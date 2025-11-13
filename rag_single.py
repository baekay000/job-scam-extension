#!/usr/bin/env python3
# rag_single.py — one-shot offline RAG over ./data/*.txt
# Prints plain text: "Verdict: ..." + "Reasons:" bullets.

import sys, os, re, glob, subprocess
from pathlib import Path
from typing import List, Tuple

DATA_DIR = Path("data")
MODEL = os.environ.get("RAG_MODEL", "mistral:7b")  # use mistral for RAG too
TOP_K = int(os.environ.get("RAG_TOPK", "4"))       # a touch more recall
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK", "600"))
CHUNK_OVERLAP = int(os.environ.get("RAG_OVERLAP", "120"))
MAX_CONTEXT_CHARS = int(os.environ.get("RAG_CTX_CHARS", "4000"))
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

def _forced_rf_gf(passages, metas, max_per_file=2):
    """Always include a few RF/GF chunks so the model has the checklist."""
    keep = []
    for i, m in enumerate(metas):
        base = m.split("#", 1)[0].lower()
        if base in ("redflags.txt", "greenflags.txt"):
            keep.append(i)
    rf = [i for i in keep if metas[i].lower().startswith("redflags.txt")][:max_per_file]
    gf = [i for i in keep if metas[i].lower().startswith("greenflags.txt")][:max_per_file]
    return rf + gf

def _ollama_run(prompt: str, model=MODEL, timeout=OLLAMA_TIMEOUT) -> str:
    res = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout
    )
    return (res.stdout or "").strip()

def _standardize_output(raw: str) -> str:
    """Coerce model output into the exact two-section format we parse downstream."""
    if not raw:
        return "Verdict: Uncertain\nReasons:\n- Empty model output"
    t = raw.strip()
    t = re.sub(r"\*\*|__", "", t)        # strip markdown bold/underline
    t = re.sub(r"</?[^>]+>", "", t)      # strip simple HTML tags
    m = re.search(r"(?im)^\s*verdict:\s*(real|fake|uncertain)\b", t)
    if m:
        verdict = m.group(1).capitalize()
    else:
        low = t.lower()
        if re.search(r"\bfake\b", low) and not re.search(r"\breal\b", low):
            verdict = "Fake"
        elif re.search(r"\breal\b", low) and not re.search(r"\bfake\b", low):
            verdict = "Real"
        elif "uncertain" in low or "unknown" in low:
            verdict = "Uncertain"
        else:
            verdict = "Uncertain"

    reasons = []
    in_reasons = False
    for line in t.splitlines():
        ls = line.strip()
        if re.match(r"(?i)^\s*reasons\s*:\s*$", ls):
            in_reasons = True
            continue
        if in_reasons and ls.startswith("-"):
            reasons.append(ls)
        if in_reasons and not ls.startswith("-") and ls:
            break
    if not reasons:
        # fallback: extract a couple short explanatory lines
        for ls in t.splitlines():
            if 5 <= len(ls) <= 200 and not ls.lower().startswith("verdict"):
                reasons.append(f"- {ls.strip()}")
            if len(reasons) >= 3:
                break
    reasons = reasons[:3] if reasons else ["- Model did not provide reasons"]
    return "Verdict: " + verdict + "\nReasons:\n" + "\n".join(reasons)

def _rule_prefilter(job_text: str):
    """Skip the LLM on obvious scams for speed & fewer 'Uncertain's."""
    t = job_text.lower()
    hits = []
    def hit(code): hits.append(code)
    if "telegram" in t or "whatsapp" in t: hit("RF-04")
    if "training fee" in t or "pay for equipment" in t or "cashier's check" in t: hit("RF-04")
    if "ssn" in t or "social security" in t or "bank account" in t or "passport" in t: hit("RF-05")
    if "no interview" in t or "hired today" in t: hit("RF-04")
    if re.search(r"\$\s?\d{2,},?\d{0,3}\s*(?:/|per)?\s?(?:hour|hr)\b", t) and "no experience" in t:
        hit("RF-03")
    if "limited slots" in t or "act in the next" in t: hit("RF-06")
    if hits:
        return "Verdict: Fake\nReasons:\n- Obvious red flags: " + ", ".join(hits)
    return None

def _make_prompt(context: str, job_text: str) -> str:
    # Relaxed: use CONTEXT *and* JOB POSTING; same output rules as baseline.
    return f"""You are a careful reviewer for job posting fraud.
Use the CONTEXT (checklists/examples) to guide your judgment, and use the JOB POSTING directly for evidence.
If signals are weak or contradictory, return Uncertain.

STRICT OUTPUT RULES:
- No markdown.
- Print exactly two sections: 'Verdict:' then 'Reasons:' with 1-3 bullets.
- Verdict must be exactly one of: Real, Fake, Uncertain.

CONTEXT:
{context}

JOB POSTING:
{job_text}

Return EXACTLY this:

Verdict: Real|Fake|Uncertain
Reasons:
- short reason #1 (cite phrase from JOB POSTING or CONTEXT)
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

    # Obvious scam shortcut
    prefake = _rule_prefilter(job_text)
    if prefake:
        print(prefake, flush=True)
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

    # Always prepend a few RF/GF chunks
    forced = _forced_rf_gf(passages, metas, max_per_file=2)
    seen = set()
    final_idxs = []
    for i in forced + idxs:
        if i not in seen:
            final_idxs.append(i); seen.add(i)

    top_chunks = [f"[{metas[i]}]\n{passages[i]}" for i in final_idxs]
    context = "\n\n".join(top_chunks)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]

    prompt = _make_prompt(context, q)
    out = _ollama_run(prompt, MODEL)
    print(_standardize_output(out), flush=True)

if __name__ == "__main__":
    main()
