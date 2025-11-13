#!/usr/bin/env python3
# rag_single.py — one-shot offline RAG over ./data/*.txt
# Prints plain text for easy embedding into a chrome extension popup.

import sys, os, re, glob, subprocess
from pathlib import Path
from typing import List, Tuple

DATA_DIR = Path("data")
MODEL = os.environ.get("RAG_MODEL", "phi3")  # e.g., phi3, mistral, llama3
TOP_K = int(os.environ.get("RAG_TOPK", "3"))
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK", "600"))
CHUNK_OVERLAP = int(os.environ.get("RAG_OVERLAP", "120"))
MAX_CONTEXT_CHARS = int(os.environ.get("RAG_CTX_CHARS", "3000"))
OLLAMA_TIMEOUT = int(os.environ.get("RAG_OLLAMA_TIMEOUT", "60"))

def _read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _load_docs() -> List[Tuple[str, str]]:
    pats = [
        str(DATA_DIR / "*.txt"),
        str(DATA_DIR / "checklists" / "*.txt"),
        str(DATA_DIR / "exemplars" / "*.txt"),
        str(DATA_DIR / "playbooks" / "*.txt"),
        str(DATA_DIR / "rules" / "*.txt"),
        str(DATA_DIR / "resources" / "*.txt"),
        str(DATA_DIR / "studies" / "*.txt"),
    ]
    docs = []
    for pat in pats:
        for fp in glob.glob(pat):
            try:
                t = _read_txt(Path(fp)).strip()
                if t:
                    docs.append((Path(fp).name, t))
            except Exception:
                pass
    return docs

def _chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        chunks.append(text[i:i+size])
        i += step
    return chunks

def _build_corpus(docs: List[Tuple[str, str]]):
    passages, metas = [], []
    for name, txt in docs:
        for idx, ch in enumerate(_chunk_text(txt)):
            passages.append(ch)
            metas.append(f"{name}#chunk{idx}")
    return passages, metas

def _retrieve(passages: List[str], query: str, top_k=TOP_K) -> List[int]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(passages + [query])
    sims = cosine_similarity(X[-1], X[:-1]).flatten()
    order = sims.argsort()[::-1][:top_k]
    return order.tolist()

def _ollama_run(prompt: str, model=MODEL, timeout=OLLAMA_TIMEOUT) -> str:
    # Simple non-stream run; keep defaults (low temp models recommended)
    res = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout
    )
    return (res.stdout or "").strip()

def _make_prompt(context: str, job_text: str) -> str:
    # Strict, short, and returns plain text.
    return f"""You are a careful reviewer for job posting fraud. Use ONLY the CONTEXT to judge the JOB POSTING.
If the context is insufficient, return Uncertain.

CONTEXT:
{context}

JOB POSTING:
{job_text}

Return EXACTLY this format:

Verdict: Real|Fake|Uncertain
Reasons:
- short reason #1 (cite brief phrase from context)
- short reason #2
- short reason #3 (optional)
""".strip()

def main():
    # Input: --text "...", --file path, or stdin
    args = sys.argv[1:]
    job_text = ""
    if "--text" in args:
        i = args.index("--text")
        if i+1 < len(args): job_text = args[i+1]
    elif "--file" in args:
        i = args.index("--file")
        if i+1 < len(args): job_text = Path(args[i+1]).read_text(encoding="utf-8", errors="ignore")
    else:
        job_text = sys.stdin.read()

    job_text = (job_text or "").strip()
    if not job_text:
        print("Verdict: Uncertain\nReasons:\n- No job text provided", flush=True)
        sys.exit(0)

    if not DATA_DIR.exists():
        print("Verdict: Uncertain\nReasons:\n- Missing ./data directory", flush=True)
        sys.exit(0)

    docs = _load_docs()
    if not docs:
        print("Verdict: Uncertain\nReasons:\n- No .txt documents in ./data", flush=True)
        sys.exit(0)

    passages, metas = _build_corpus(docs)
    q = re.sub(r"\s+", " ", job_text)[:1500]
    idxs = _retrieve(passages, q, top_k=TOP_K)
    top_chunks = [f"[{metas[i]}]\n{passages[i]}" for i in idxs]

    context = "\n\n".join(top_chunks)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]

    prompt = _make_prompt(context, q)
    out = _ollama_run(prompt, MODEL)
    # Print raw (plain text), which the wrapper will parse
    print(out, flush=True)

if __name__ == "__main__":
    main()
