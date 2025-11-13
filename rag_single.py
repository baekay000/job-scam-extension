#!/usr/bin/env python3
# rag_single_llm_simple.py — minimal LLM-backed RAG (Mistral via Ollama)
# Pipeline:
#   1) Load ./data/*.txt → chunk w/ overlap
#   2) TF-IDF (1–2 grams) → cosine retrieve top-k
#   3) Tag sources (RED/GREEN/FAKE-EX/REAL-EX/OTHER)
#   4) Prompt Mistral with short hints + top-k context + job post
#   5) Print: Verdict + short human-explainable Reasons (1–3 bullets)

import sys, os, re, glob, subprocess, json
from pathlib import Path
from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---- Config (override with env) ----
DATA_DIR        = Path(os.environ.get("RAG_DATA_DIR", "data"))
MODEL           = os.environ.get("RAG_MODEL", "mistral:7b")   # ensure: `ollama pull mistral:7b`
TOP_K           = int(os.environ.get("RAG_TOPK", "3"))
CHUNK_SIZE      = int(os.environ.get("RAG_CHUNK", "550"))
CHUNK_OVERLAP   = int(os.environ.get("RAG_OVERLAP", "120"))
MAX_JOB_CHARS   = int(os.environ.get("RAG_JOB_CHARS", "1800"))
MAX_CTX_CHARS   = int(os.environ.get("RAG_CTX_CHARS", "2800"))
OLLAMA_TIMEOUT  = int(os.environ.get("RAG_OLLAMA_TIMEOUT", "180"))  # first call can be slow
RETRY_WARMUP    = int(os.environ.get("RAG_RETRY_WARMUP", "1"))      # 1 = one warmup retry

# ---- IO helpers ----
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
    docs = []
    for fp in sorted(glob.glob(str(DATA_DIR / "*.txt"))):
        t = read_txt(Path(fp)).strip()
        if t:
            docs.append((Path(fp).name, t))
    return docs

def build_corpus(docs: List[Tuple[str, str]]):
    passages, metas = [], []
    for name, txt in docs:
        for idx, ch in enumerate(chunk_text(txt)):
            passages.append(ch)
            metas.append(f"{name}#chunk{idx}")
    return passages, metas

def source_tag(filename: str) -> str:
    f = filename.lower()
    if "redflags" in f:               return "RED"
    if "greenflags" in f:             return "GREEN"
    if "fake_job_exemplars" in f:     return "FAKE-EX"
    if "real_job_exemplars" in f:     return "REAL-EX"
    return "OTHER"

def retrieve(passages: List[str], query: str, top_k=TOP_K) -> List[int]:
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), sublinear_tf=True, min_df=1, max_df=0.98)
    X = vec.fit_transform(passages + [query])
    sims = cosine_similarity(X[-1], X[:-1]).flatten()
    order = sims.argsort()[::-1][:top_k]
    return order.tolist()

def make_prompt(context_blocks: List[Tuple[str, str]], job_text: str) -> str:
    """
    context_blocks: list of (tag, text) for the top-k chunks
    We provide a tiny nudge: chunks from RED/FAKE-EX encourage Fake; GREEN/REAL-EX encourage Real.
    """
    tag_counts = {"RED":0,"FAKE-EX":0,"GREEN":0,"REAL-EX":0,"OTHER":0}
    for tag, _ in context_blocks:
        tag_counts[tag] = tag_counts.get(tag,0) + 1

    # Small, human-readable hint for the LLM (no hard rules)
    hint_lines = []
    if tag_counts["RED"] or tag_counts["FAKE-EX"]:
        hint_lines.append(f"- Evidence leaning FAKE: {tag_counts['RED']} from RED FLAGS, {tag_counts['FAKE-EX']} from FAKE EXEMPLARS")
    if tag_counts["GREEN"] or tag_counts["REAL-EX"]:
        hint_lines.append(f"- Evidence leaning REAL: {tag_counts['GREEN']} from GREEN FLAGS, {tag_counts['REAL-EX']} from REAL EXEMPLARS")
    if not hint_lines:
        hint_lines.append("- Evidence is mixed; rely on the job text and the retrieved context.")

    ctx_strs = []
    for i, (tag, text) in enumerate(context_blocks, 1):
        ctx_strs.append(f"[{tag} #{i}] {text}")

    context_joined = "\n\n".join(ctx_strs)
    if len(context_joined) > MAX_CTX_CHARS:
        context_joined = context_joined[:MAX_CTX_CHARS]

    return f"""You are classifying a job posting as Real or Fake.
Use the CONTEXT blocks (tagged RED/GREEN/FAKE-EX/REAL-EX/OTHER) to inform your reasoning.
If many RED/FAKE-EX chunks appear, lean toward Fake. If many GREEN/REAL-EX chunks appear, lean toward Real.
However, prefer direct evidence from the JOB POSTING when available.

GUIDANCE:
{chr(10).join(hint_lines)}

CONTEXT:
{context_joined}

JOB POSTING:
{job_text}

OUTPUT FORMAT (exactly):
Verdict: Real|Fake
Reasons:
- reason #1 (quote tiny snippet from CONTEXT or JOB POSTING if useful)
- reason #2 (optional)
- reason #3 (optional)
""".strip()

def ollama_run(prompt: str, model=MODEL, timeout=OLLAMA_TIMEOUT) -> str:
    """Call Mistral via Ollama CLI with optional warmup retry."""
    cmd = ["ollama", "run", model]
    tries = 1 + max(0, RETRY_WARMUP)
    last_err = ""
    for t in range(tries):
        try:
            res = subprocess.run(
                cmd, input=prompt, text=True, capture_output=True, timeout=timeout
            )
            out = (res.stdout or "").strip()
            if out:
                return out
            last_err = (res.stderr or "").strip()
        except subprocess.TimeoutExpired:
            last_err = f"timeout after {timeout}s"
        # warmup ping before retry (load model)
        try:
            subprocess.run(["ollama", "run", model, "ok"], text=True, capture_output=True, timeout=30)
        except Exception:
            pass
    return f"Verdict: Fake\nReasons:\n- The model did not respond in time ({last_err})."

def parse_and_print(raw: str):
    """Normalize model output → print Verdict + Reasons bullets (1–3)."""
    t = (raw or "").strip()
    t = re.sub(r"\*\*|__", "", t)
    t = re.sub(r"</?[^>]+>", "", t)

    m = re.search(r"(?im)^\s*verdict:\s*(real|fake)\b", t)
    verdict = m.group(1).capitalize() if m else None

    reasons = []
    # capture lines under "Reasons:" that look like bullets
    block = re.split(r"(?im)^\s*reasons\s*:\s*$", t)
    if len(block) > 1:
        for line in block[1].splitlines():
            ls = line.strip()
            if ls.startswith("-") or ls.startswith("•"):
                reasons.append(re.sub(r"^[\-\•]\s*", "- ", ls))
            elif ls and len(reasons) > 0:
                # stop at first non-bullet after starting bullets
                break

    if not verdict:
        # fallback: nudge based on the word presence, but keep it rare
        low = t.lower()
        verdict = "Fake" if ("fake" in low and "real" not in low) else "Real"

    if not reasons:
        reasons = ["- The wording aligns more with this category given the retrieved context and job details."]

    print(f"Verdict: {verdict}")
    print("Reasons:")
    for r in reasons[:3]:
        print(r)

# ---- Main ----
def main():
    # Input: --text "...", --file path, or stdin
    args = sys.argv[1:]
    job_text = ""
    if "--text" in args:
        i = args.index("--text"); 
        if i+1 < len(args): job_text = args[i+1]
    elif "--file" in args:
        i = args.index("--file"); 
        if i+1 < len(args): job_text = Path(args[i+1]).read_text(encoding="utf-8", errors="ignore")
    else:
        job_text = sys.stdin.read()

    # Clean & trim the job text
    job_text = (job_text or "")
    q = re.sub(r'https?://\S+|www\.\S+|[\w\.-]+@[\w\.-]+', ' ', job_text)
    q = re.sub(r'\s+', ' ', q).strip()[:MAX_JOB_CHARS]
    if not q:
        print("Verdict: Fake")
        print("Reasons:\n- The posting is empty; there is no information to evaluate.")
        return

    # Build corpus
    docs = load_docs()
    passages, metas = build_corpus(docs) if docs else ([], [])
    if passages:
        idxs = retrieve(passages, q, top_k=TOP_K)
        blocks = []
        for i in idxs:
            fname = metas[i].split("#", 1)[0]
            tag = source_tag(fname)
            blocks.append((tag, passages[i]))
    else:
        # no context; still let Mistral decide just from post
        blocks = []

    prompt = make_prompt(blocks, q)
    raw = ollama_run(prompt, MODEL)
    parse_and_print(raw)

if __name__ == "__main__":
    main()
