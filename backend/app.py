

import os
import json
import base64
import subprocess
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

from rag_utils import (
    load_embedder, init_chroma, get_or_create_collection,
    extract_text_from_base64_pdf, extract_text_from_plain_text,
    extract_text_from_youtube, build_chunks, add_chunks_to_chroma,
    query_chroma, strip_think_tags
)

# --- Config & Init ---
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", DEFAULT_CORS).split(",")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "study_chunks")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_PROVIDER = os.getenv("LLM_API_PROVIDER", "")
LLM_API_MODEL = os.getenv("LLM_API_MODEL")

app = Flask(__name__)
# During local development allow common localhost dev origins by default.
# You can override with the CORS_ORIGINS env var (comma-separated list).
if os.getenv("FLASK_ENV") == "development":
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
else:
    CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

# Ensure persistence dirs
os.makedirs(CHROMA_PATH, exist_ok=True)

# RAG engine
embedder = load_embedder(EMBED_MODEL)
client = init_chroma(CHROMA_PATH)
collection = get_or_create_collection(client, COLLECTION_NAME)

def build_llm_prompt(context_items, question: str, conversation: list | None = None) -> str:
    """
    FINAL RAG TUTOR PROMPT:
    This version enforces:
    - NoteMind AI role
    - Context-first teaching
    - Automatic topic detection
    - NO refusal lines
    - Answers all question types
    - Uses general knowledge ONLY when context fails
    """

    lines = []

    # ----------------------------------------------------------
    # ROLE + BEHAVIOR INSTRUCTIONS
    # ----------------------------------------------------------
    lines.append(
        "ROLE: You are NoteMind AI, an intelligent tutor for students.\n"
        "The student uploads learning materials (PDF/text/YouTube transcripts). "
        "These materials are chunked using RAG. Your job is to TEACH strictly from these chunks.\n\n"

        "BEHAVIOR RULES:\n"
        "1. ALWAYS assume the uploaded content is the student's study material or textbook.\n"
        "2. ALWAYS analyze the available CONTEXT (chunks) before answering.\n"
        "3. ALWAYS answer using the context FIRST. Treat it as the main syllabus.\n"
        "4. For ANY question (MCQ, summary, explanation, general question), "
        "always try to relate the answer to the uploaded content’s topic.\n"
        "5. If the context is incomplete, vague, or unrelated, infer the TOPIC from it and still answer.\n"
        "6. ONLY if the answer truly cannot be derived from context, use general knowledge — NEVER say 'no context'.\n"
        "7. NEVER repeat refusal-like lines from the context (such as 'I cannot answer', 'no context provided').\n"
        "8. NEVER tell the user that context is missing. ALWAYS provide a useful final answer.\n"
        "9. MCQs, summaries, short notes, and explanations are ALWAYS allowed.\n"
        "10. If the user asks a general question like 'Define X', STILL use the content as the primary source.\n"
    )

    # ----------------------------------------------------------
    # CONTEXT SECTION
    # ----------------------------------------------------------
    lines.append("\n### STUDY MATERIAL (CONTEXT):")

    if context_items:
        for hit in context_items:
            md = hit["metadata"]
            title = md.get("title", "source")
            idx = md.get("idx", 0)

            content = hit["content"]

            # Remove refusal text found inside PDFs/YT transcripts
            refusal_markers = [
                "I cannot", "cannot answer", "I'm unable", "not sufficient context",
                "I need more context", "as an AI", "I am not allowed", "unable to generate",
                "I can't", "follow these rules"
            ]
            for phrase in refusal_markers:
                content = content.replace(phrase, "")

            lines.append(f"[{title}#{idx}] {content}\n")
    else:
        lines.append("[No retrieved chunks — You MUST still answer using general knowledge.]\n")

    # ----------------------------------------------------------
    # CONVERSATION HISTORY
    # ----------------------------------------------------------
    if conversation:
        lines.append("\n### CONVERSATION HISTORY:")
        for msg in conversation:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")

    # ----------------------------------------------------------
    # USER QUESTION
    # ----------------------------------------------------------
    lines.append("\n### QUESTION:")
    lines.append(question.strip())

    # ----------------------------------------------------------
    # FINAL ANSWER
    # ----------------------------------------------------------
    lines.append(
        "\n### FINAL ANSWER:\n"
        "Answer as NoteMind AI, a helpful intelligent tutor. Use the uploaded study content FIRST, "
        "infer the topic if needed, and give the best educational answer possible."
    )

    return "\n".join(lines)


def run_ollama(prompt: str) -> str:
    # If a HTTP LLM API is configured, prefer it (supports Google Generative API)
    provider = (LLM_API_PROVIDER or "").lower()
    if LLM_API_URL and LLM_API_KEY and provider in ("google", "gemini", "generativelanguage"):
        # Build request to Google's Generative Language API
        # If LLM_API_URL already includes '/models/..:generateContent', use it directly; otherwise compose.
        model = LLM_API_MODEL or "gemini-1.5-flash"
        base = LLM_API_URL.rstrip("/")
        if "/models/" in base and ":generateContent" in base:
            url = base
            params = {"key": LLM_API_KEY}
        else:
            url = f"{base}/models/{model}:generateContent"
            params = {"key": LLM_API_KEY}
        # Payload per Google GenAI: contents with role + parts.text
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
            },
        }
        try:
            resp = requests.post(url, params=params, json=payload, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Google LLM API request failed: {e}")

        try:
            data = resp.json()
        except Exception:
            return strip_think_tags(resp.text)

        # Extract text from Google GenAI response
        if isinstance(data, dict):
            candidates = data.get("candidates")
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                first = candidates[0]
                if isinstance(first, dict):
                    # Newer schema: candidates[0].content.parts[].text
                    content = first.get("content")
                    if isinstance(content, dict):
                        parts = content.get("parts")
                        if isinstance(parts, list):
                            texts = []
                            for p in parts:
                                if isinstance(p, dict) and "text" in p:
                                    texts.append(p["text"])
                            if texts:
                                return strip_think_tags("\n".join(texts))
                    # Older fallbacks
                    if "text" in first and isinstance(first["text"], str):
                        return strip_think_tags(first["text"])

        # Last resort: stringify JSON
        return strip_think_tags(json.dumps(data))

    # Fallback: Ollama CLI
    try:
        # Force UTF-8 encoding for input/output to avoid Windows 'charmap' UnicodeEncodeError
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except UnicodeEncodeError:
        # Fallback: encode to bytes and run without text mode
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt.encode("utf-8", errors="replace"),
            capture_output=True,
        )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, (bytes, bytearray)) else result.stderr
        raise RuntimeError(stderr or "ollama failed")

    stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, (bytes, bytearray)) else result.stdout
    return strip_think_tags(stdout)

# --- API Endpoints ---

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": OLLAMA_MODEL})

@app.route("/api/ingest", methods=["POST"])
def ingest():
    """
    Expected JSON:
    {
      "items": [
        { "type": "pdf", "name": "file.pdf", "dataBase64": "data:application/pdf;base64,..." },
        { "type": "text", "name": "notes.txt", "text": "raw text" },
        { "type": "youtube", "url": "https://www.youtube.com/watch?v=VIDEOID", "title": "optional" }
      ]
    }
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"ok": False, "error": "No items provided"}), 400

    total_chunks = 0
    ingested = []

    # Optional conversation id to tag ingested chunks
    conversation_id = data.get("conversationId")
    for item in items:
        itype = item.get("type")
        title = item.get("name") or item.get("title") or itype

        try:
            if itype == "pdf":
                b64 = item.get("dataBase64")
                if not b64:
                    return jsonify({"ok": False, "error": "PDF missing dataBase64"}), 400
                text = extract_text_from_base64_pdf(b64)
                chunks = build_chunks(text, title=title, source_type="pdf", source_id=title)

            elif itype == "text":
                txt = item.get("text", "")
                text = extract_text_from_plain_text(txt)
                chunks = build_chunks(text, title=title, source_type="text", source_id=title)

            elif itype == "youtube":
                url = item.get("url", "")
                if not url:
                    return jsonify({"ok": False, "error": "YouTube missing url"}), 400
                text, vid = extract_text_from_youtube(url)
                yt_title = title if title else f"youtube:{vid}"
                chunks = build_chunks(text, title=yt_title, source_type="youtube", source_id=vid)

            else:
                return jsonify({"ok": False, "error": f"Unsupported type: {itype}"}), 400

            count = add_chunks_to_chroma(collection, embedder, chunks, conversation_id=conversation_id)
            total_chunks += count
            ingested.append({"type": itype, "title": title, "chunks": count})

        except Exception as e:
            return jsonify({"ok": False, "error": f"Ingest failed for {title}: {e}"}), 500

    return jsonify({"ok": True, "ingested": ingested, "total_chunks": total_chunks})

@app.route("/api/ask", methods=["POST"])
def ask():
    """
    Expected JSON:
    {
      "question": "string",
      "topK": 6
    }
    """
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    top_k = int(data.get("topK", 6))
    conversation = data.get("conversation")

    if not question:
        return jsonify({"ok": False, "error": "Missing question"}), 400

    # Check if there is any indexed data; allow fallback to model knowledge if none exists
    count = collection.count()
    allow_fallback = False
    if count == 0:
        # No data indexed — allow the model to answer from its own knowledge
        allow_fallback = True

    try:
        # Allow scoping retrieval to specific conversation(s)/material(s) if provided
        conversation_ids = data.get("conversationIds") or data.get("conversationId")
        # conversation_ids may be a single id or a list
        hits = query_chroma(collection, embedder, question, top_k, conversation_id=conversation_ids)
        # If retrieval returns nothing, allow fallback to model knowledge
        if not hits:
            allow_fallback = True
        
        # Debug: log retrieval results
        print(f"[DEBUG] Question: {question}")
        print(f"[DEBUG] Conversation IDs filter: {conversation_ids}")
        print(f"[DEBUG] Retrieved {len(hits)} chunks from ChromaDB")
        if hits:
            print(f"[DEBUG] First chunk preview: {hits[0]['content'][:200]}...")
        else:
            print(f"[DEBUG] WARNING: No chunks retrieved! Collection has {count} total chunks.")
        
        prompt = build_llm_prompt(hits, question, conversation=conversation)
        print(f"[DEBUG] Prompt length: {len(prompt)} chars")
        print(f"[DEBUG] Prompt preview (first 500 chars):\n{prompt[:500]}")
        
        answer = run_ollama(prompt)

        # Build citations
        citations = []
        for h in hits:
            md = h["metadata"]
            citations.append({
                "title": md.get("title", "source"),
                "documentId": md.get("source_id", ""),
                "chunkIndex": md.get("idx", 0)
            })

        return jsonify({"ok": True, "answer": answer, "citations": citations})

    except Exception as e:
        return jsonify({"ok": False, "error": f"Answer failed: {e}"}), 500

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
