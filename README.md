# NoteMind AI

NoteMind AI — an intelligent study companion powered by Vite + React frontend with Python backend for
retrieval-augmented generation (RAG). The backend ingests PDFs, plain text,
and YouTube transcripts, stores embeddings in a local ChromaDB, and queries a
local LLM (via Google Gemini API) to answer user questions.

Quick start

1. Frontend

```powershell
cd <repo-root>
npm install
npm run dev
# open http://localhost:8080
```

2. Backend (optional)

```powershell
cd <repo-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt --prefer-binary
Set-Location .\backend
python app.py
# health: GET http://127.0.0.1:5000/api/health
```

If you don't need the backend, you can ignore the `backend/` folder and run
only the frontend.

What changed from the template

- Removed project-specific generated branding and external links.
 - Set `index.html` title to "NoteMind AI" and removed external Lovable image.

If you'd like, I can make additional cleanups (remove temporary logs,
remove unused dev dependencies such as `lovable-tagger`, or add a small
integration test that runs ingest+ask). Reply with what you'd like removed
next and I'll apply it.
