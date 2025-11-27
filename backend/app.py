

import os
import json
import base64
import subprocess
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

# --- Helpers ---
def build_llm_prompt(context_items, question: str, conversation: list | None = None) -> str:
    # Build grounded prompt with citations
    lines = []
    lines.append("You are a precise, helpful AI tutor and conversational assistant. Use the provided CONTEXT below to answer the question when possible.")
    lines.append("If the context is insufficient, you may answer using your general knowledge — be explicit about when you are using external knowledge vs. the provided CONTEXT. When a conversation history is provided, respond in a friendly, conversational manner and respect the conversational context.")
    lines.append("Cite sources inline like (title#chunkIndex).\n")
    lines.append("CONTEXT:")
    for hit in context_items:
        md = hit["metadata"]
        title = md.get("title", "source")
        idx = md.get("idx", 0)
        lines.append(f"[{title}#{idx}] {hit['content']}\n")
    # If conversation history is provided, include it before the new question
    if conversation:
        lines.append("\nCONVERSATION_HISTORY:")
        for msg in conversation:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")

    lines.append("\nQUESTION:")
    lines.append(question.strip())
    lines.append("\nANSWER:")
    return "\n".join(lines)

def run_ollama(prompt: str) -> str:
    # Requires: ollama pull deepseek-r1:7b
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

            count = add_chunks_to_chroma(collection, embedder, chunks)
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
        hits = query_chroma(collection, embedder, question, top_k)
        # If retrieval returns nothing, allow fallback to model knowledge
        if not hits:
            allow_fallback = True
        prompt = build_llm_prompt(hits, question, conversation=conversation)
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
