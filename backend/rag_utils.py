import os
import re
import tempfile
import shutil
import subprocess
from urllib.parse import urlparse, parse_qs
import base64
import io
from typing import List, Dict, Tuple
from dataclasses import dataclass
from tqdm import tqdm

from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


@dataclass
class Chunk:
    content: str
    title: str
    idx: int
    source_type: str
    source_id: str


def load_embedder(model_name: str):
    return SentenceTransformer(model_name)


def init_chroma(path: str):
    client = chromadb.PersistentClient(path=path, settings=Settings(allow_reset=False))
    return client


def get_or_create_collection(client, name: str):
    # We’ll pass embeddings explicitly, so no embedding function is needed here
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def _normalize_text(txt: str) -> str:
    txt = txt.replace("\x00", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf (pure-Python)."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                # fallback: empty string for problematic pages
                pages.append("")
        return _normalize_text("\n\n".join(pages))
    except Exception:
        # If pypdf fails, return empty string
        return ""


def extract_text_from_base64_pdf(b64: str) -> str:
    pdf_bytes = base64.b64decode(b64.split(",")[-1])
    return extract_text_from_pdf_bytes(pdf_bytes)


def extract_text_from_plain_text(txt: str) -> str:
    return _normalize_text(txt or "")


def youtube_id_from_url(url: str) -> str:
    # Parse common YouTube URL formats and return the video ID
    if not url:
        raise ValueError("Empty YouTube URL")

    # If input already looks like a plain ID (11 chars typical), return it
    if re.fullmatch(r"[A-Za-z0-9_\-]{11}", url):
        return url

    # Try to parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid YouTube URL: {url}")

    # youtu.be short links: path contains the id
    if parsed.netloc and parsed.netloc.endswith("youtu.be"):
        vid = parsed.path.lstrip("/")
        if re.fullmatch(r"[A-Za-z0-9_\-]{6,}", vid):
            return vid

    # standard youtube watch URLs: v= query param
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]

    # shorts or embed paths
    m = re.search(r"/(?:shorts|embed)/([A-Za-z0-9_\-]{6,})", parsed.path)
    if m:
        return m.group(1)

    # final fallback: try to extract common patterns directly
    # Also strip known extra query params (e.g., playlist) and anchors
    clean = url.split("#")[0].split("&list=")[0]
    m2 = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_\-]{6,})", clean)
    if m2:
        return m2.group(1)

    raise ValueError(f"Could not extract YouTube video id from: {url}")


def extract_text_from_youtube(url: str) -> Tuple[str, str]:
    vid = youtube_id_from_url(url)
    try:
        # Try explicit transcript (human-created)
        transcript_list = YouTubeTranscriptApi.get_transcript(vid, languages=["en"])
        text = " ".join([seg.get("text", "") for seg in transcript_list])
        return _normalize_text(text), vid
    except (NoTranscriptFound, TranscriptsDisabled):
        # Try auto-generated transcripts (may still fail)
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
            auto = transcript_list.find_generated_transcript(["en"])
            entries = auto.fetch()
            text = " ".join([seg.get("text", "") for seg in entries])
            return _normalize_text(text), vid
        except Exception as e:
            # Re-raise a clearer error for the caller
            raise RuntimeError(f"No transcript available for video {vid}: {e}")
    except ValueError as ve:
        # propagate URL parsing errors clearly
        raise RuntimeError(str(ve))
    except Exception as e:
        # Generic failure: sometimes YouTube returns an HTML error/consent page
        # which leads to XML parsing errors like 'no element found: line 1, column 0'.
        # Try a fallback using `yt-dlp` to download auto subtitles (if installed).
        try:
            if shutil.which("yt-dlp") is None:
                raise RuntimeError(f"{e} -- yt-dlp not available for fallback. Install `yt-dlp` and `ffmpeg` to enable subtitle/audio fallbacks.")

            tmpdir = tempfile.mkdtemp(prefix=f"yt_{vid}_")
            out_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--sub-format", "vtt",
                "-o", out_template,
                f"https://www.youtube.com/watch?v={vid}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            # If yt-dlp failed, surface its stderr as part of the error
            if proc.returncode != 0:
                stderr = proc.stderr or proc.stdout
                raise RuntimeError(f"yt-dlp failed: {stderr}")

            # Find the .vtt file that yt-dlp wrote
            vtt_file = None
            for fname in os.listdir(tmpdir):
                if fname.startswith(vid) and fname.lower().endswith(".vtt"):
                    vtt_file = os.path.join(tmpdir, fname)
                    break

            if vtt_file:
                with open(vtt_file, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = []
                    for line in fh:
                        line = line.strip()
                        # Skip WEBVTT header and timestamp lines
                        if not line or line.upper().startswith("WEBVTT"):
                            continue
                        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3} -->", line) or "-->" in line:
                            continue
                        # Skip numeric cue indexes
                        if re.fullmatch(r"\d+", line):
                            continue
                        lines.append(line)
                    text = " ".join(lines)
                shutil.rmtree(tmpdir, ignore_errors=True)
                if text.strip():
                    return _normalize_text(text), vid
                else:
                    raise RuntimeError("yt-dlp succeeded but no subtitle text was extracted.")
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)
                raise RuntimeError("yt-dlp ran but no .vtt subtitle file was produced for the video.")
        except Exception as fallback_exc:
            # Combine the original error and fallback error for clarity
            raise RuntimeError(f"Failed to fetch transcript for {vid}: {e} -- fallback error: {fallback_exc}")


def tokenize_estimate(text: str) -> int:
    # rough heuristic: ~4 chars per token
    return max(1, len(text) // 4)


def chunk_text(text: str, target_tokens=750, overlap_tokens=150) -> List[str]:
    # paragraph-aware sliding window by character length (approx tokens * 4)
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = []
    current_chars = 0
    max_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4

    for p in parts:
        if current_chars + len(p) + 2 <= max_chars:
            current.append(p)
            current_chars += len(p) + 2
        else:
            if current:
                chunks.append("\n\n".join(current))
                # build overlap
                keep = []
                keep_chars = 0
                for para in reversed(current):
                    if keep_chars + len(para) + 2 <= overlap_chars:
                        keep.insert(0, para)
                        keep_chars += len(para) + 2
                    else:
                        break
                current = keep + [p]
                current_chars = sum(len(x) + 2 for x in current)
            else:
                # very long single paragraph
                chunks.append(p[:max_chars])
                current = [p[max_chars - overlap_chars:]]
                current_chars = len(current[0])

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_chunks(text: str, title: str, source_type: str, source_id: str) -> List[Chunk]:
    pieces = chunk_text(text)
    out = []
    for i, c in enumerate(pieces):
        out.append(Chunk(content=c, title=title, idx=i, source_type=source_type, source_id=source_id))
    return out


def add_chunks_to_chroma(collection, embedder, chunks: List[Chunk]):
    docs = [c.content for c in chunks]
    ids  = [f"{c.source_type}:{c.source_id}:{c.idx}" for c in chunks]
    metas = [{"title": c.title, "source_type": c.source_type, "source_id": c.source_id, "idx": c.idx} for c in chunks]
    embs = embedder.encode(docs, convert_to_numpy=True, normalize_embeddings=True).tolist()
    collection.add(documents=docs, embeddings=embs, metadatas=metas, ids=ids)
    return len(docs)


def query_chroma(collection, embedder, question: str, top_k: int = 6):
    q_emb = embedder.encode([question], convert_to_numpy=True, normalize_embeddings=True).tolist()
    res = collection.query(query_embeddings=q_emb, n_results=top_k)
    # res keys: 'ids', 'documents', 'metadatas', 'distances'
    hits = []
    for i in range(len(res["ids"][0])):
        hits.append({
            "id": res["ids"][0][i],
            "content": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "distance": res["distances"][0][i],
        })
    return hits


def strip_think_tags(txt: str) -> str:
    # DeepSeek-R1 may output <think>…</think> sections; remove them
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL|re.IGNORECASE)
    return txt.strip()
