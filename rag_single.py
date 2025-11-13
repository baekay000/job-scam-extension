#!/usr/bin/env python3
# rag_single_llm.py — tiny LLM-backed RAG (Mistral via Ollama)
# Pipeline:
#   1) Load ./data/*.txt → chunk with overlap
#   2) TF-IDF vectorize → cosine retrieve top-k
#   3) Inject top-k into prompt + job posting
#   4) Call Mistral (ollama run) to reason
#   5) Print: Verdict + one short explanation (human-friendly)

import sys, os, re, glob, subprocess
from pathlib import Path
from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------- Config (override with env vars) --------
DATA_DIR        = Path(os.environ.get("RAG_DATA_DIR", "data"))
MODEL           = os.environ.get("RAG_MODEL", "mistral:7b")   # ensure: `ollama pull mistral:7b`
TOP_K           = int(os.environ.get("RAG_TOPK", "3"))
CHUNK_SIZE      = int(os.environ.get("RAG_CHUNK", "550"))
CHUNK_OVERLAP   = int(os.environ.get("RAG_OVERLAP", "120"))
MAX_JOB_CHARS   = int(os.environ.get("RAG_JOB_CHARS", "1800"))
MAX_CTX_CHARS   = int(os.environ.get("RAG_CTX_CHARS", "2800"))
OLLAMA_TIMEOUT  = int(os.environ.get("RAG_OLLAMA_TIMEOUT", "60"))

# -------- Helpers --------
def read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    out, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        out.append(text[i:i+size])
        i += step
    return out

def load_docs() -> List[Tuple[str, str]]:
    """Load all .txt files in ./data into (name, text)."""
    docs = []
    for fp in sorted(glob.glob(str(DATA_DIR / "*.txt"))):
        t = read_txt(Path(fp)).strip()
        if t:
            docs.append((Path(fp).name, t))
    return docs

def build_corpus(docs: List[Tuple[str, str]]):
    """Return passages (chunks) and metas (file#chunk ids)."""
    passages, metas = [], []
    for name, txt in docs:
        for idx, ch in enumerate(chunk_text(txt)):
            passages.append(ch)
            metas.append(f"{name}#chunk{idx}")
    return passages, metas

def retrieve(passages: List[str], query: str, top_k=TOP_K) -> List[int]:
    """TF-IDF (1–2 grams, sublinear) + cosine; return top-k indices."""
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), sublinear_tf=True, min_df=1, max_df=0.98)
    X = vec.fit_transform(passages + [query])
    sims = cosine_similarity(X[-1], X[:-1]).flatten()
    order = sims.argsort()[::-1][:top_k]
    return order.tolist()

def make_prompt(context: str, job_text: str) -> str:
    # Keep it short & strict so parsing is trivial
    return f"""You are reviewing a job posting for authenticity using the retrieved context (checklists/examples).
Use the CONTEXT and the JOB POSTING to decide if the posting is Real or Fake.
Be decisive. If evidence is mixed, choose the better-supported of the two.

Return EXACTLY this format (no extra lines, no markdown):
Verdict: Real|Fake
Reason: one short human-readable sentence explaining why

CONTEXT:
{context}

JOB POSTING:
{job_text}
""".strip()

def ollama_run(prompt: str, model=MODEL, timeout=OLLAMA_TIMEOUT) -> str:
    """Call Mistral via Ollama CLI (no API key needed)."""
    res = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout
    )
    return (res.stdout or "").strip()

def parse_and_print(raw: str):
    """
    Accepts any model output and prints normalized:
      Verdict: Real|Fake
      Reason: <one sentence>
    Falls back conservatively if the model drifts.
    """
    text = (raw or "").strip()
    # Normalize minor markdown/HTML if present
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"</?[^>]+>", "", text)

    # Extract verdict
    m = re.search(r"(?im)^\s*verdict:\s*(real|fake)\b", text)
    verdict = m.group(1).capitalize() if m else None

    # Extract reason (single line after "Reason:")
    r = re.search(r"(?im)^\s*reason:\s*(.+)$", text)
    reason = r.group(1).strip() if r else None

    if not verdict:
        # last-resort heuristic: if "fake" appears and "real" doesn't → Fake; else Real
        low = text.lower()
        verdict = "Fake" if ("fake" in low and "real" not in low) else "Real"
        if not reason:
            reason = "Chose a fallback verdict based on the model’s wording."

    if not reason:
        reason = "The posting’s details align more with this category based on the retrieved context."

    print(f"Verdict: {verdict}")
    print(f"Reason: {reason}")

# -------- Main --------
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

    # Clean & trim the job text a bit
    job_text = (job_text or "")
    q = re.sub(r'https?://\S+|www\.\S+|[\w\.-]+@[\w\.-]+', ' ', job_text)
    q = re.sub(r'\s+', ' ', q).strip()[:MAX_JOB_CHARS]
    if not q:
        print("Verdict: Fake")
        print("Reason: The posting contains no information to evaluate.")
        return

    # Load & build corpus
    docs = load_docs()
    if not docs:
        # Still proceed with LLM but with empty context (forces model to decide from the post)
        context = ""
    else:
        passages, metas = build_corpus(docs)
        idxs = retrieve(passages, q, top_k=TOP_K)
        top_chunks = [f"[{metas[i]}]\n{passages[i]}" for i in idxs]
        context = "\n\n".join(top_chunks)
        if len(context) > MAX_CTX_CHARS:
            context = context[:MAX_CTX_CHARS]

    # Prompt → Mistral (Ollama) → print normalized
    prompt = make_prompt(context, q)
    raw = ollama_run(prompt, MODEL)
    parse_and_print(raw)

if __name__ == "__main__":
    main()
