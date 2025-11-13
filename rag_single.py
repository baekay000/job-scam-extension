#!/usr/bin/env python3
# rag_single_simple.py — minimal, fast, no-LLM "RAG"
# - Vectorize corpus (./data/*.txt)
# - Retrieve top-k passages for the input text
# - Score using exemplar similarity + simple RF/GF counts
# - Print: Verdict + Reasons (plain text)

import sys, os, re, glob
from pathlib import Path
from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path("data")
TOP_K = int(os.environ.get("RAG_TOPK", "4"))
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK", "600"))
CHUNK_OVERLAP = int(os.environ.get("RAG_OVERLAP", "120"))
MAX_JOB_CHARS = int(os.environ.get("RAG_JOB_CHARS", "2000"))

# --------- tiny helpers ----------
def _read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text: return []
    out, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        out.append(text[i:i+size])
        i += step
    return out

def _load_corpus() -> Tuple[List[str], List[str]]:
    """Return passages and metadata labels."""
    if not DATA_DIR.exists():
        return [], []
    passages, metas = [], []
    for fp in sorted(glob.glob(str(DATA_DIR / "*.txt"))):
        name = Path(fp).name
        txt = _read_txt(Path(fp)).strip()
        if not txt: 
            continue
        for idx, ch in enumerate(_chunk_text(txt)):
            passages.append(ch)
            metas.append(f"{name}#chunk{idx}")
    return passages, metas

# --------- cheap signals (regex) ----------
# Keep these very small to stay "simple"
RF_PATTERNS = [
    ("RF-04", r"\b(no interview|required today|instant hire|start immediately|telegram|whatsapp)\b"),
    ("RF-05", r"\b(ssn|social security|bank account|routing number|passport|id scan|remote desktop)\b"),
    ("RF-03", r"\$\s?\d{2,},?\d{0,3}\s*(/|per)?\s?(hour|hr)\b.*\bno experience\b"),
]
GF_PATTERNS = [
    ("GF-04", r"\b(workday|greenhouse|lever|smartrecruiters)\b"),
    ("GF-02", r"\bresponsibilities\b.*\brequirements\b"),
    ("GF-09", r"\bequal opportunity employer\b|\beeo\b"),
]

def _rf_gf_counts(job_text: str):
    t = job_text.lower()
    rf = [code for code, pat in RF_PATTERNS if re.search(pat, t)]
    gf = [code for code, pat in GF_PATTERNS if re.search(pat, t)]
    return rf, gf

# --------- simple class exemplars ----------
def _load_exemplar_sets():
    """Return strings for crude class centroids (if files exist)."""
    fake_fp = DATA_DIR / "fake_job_exemplars.txt"
    real_fp = DATA_DIR / "real_job_exemplars.txt"
    fake_txt = _read_txt(fake_fp) if fake_fp.exists() else ""
    real_txt = _read_txt(real_fp) if real_fp.exists() else ""
    return fake_txt.strip(), real_txt.strip()

# --------- main simple RAG ----------
def main():
    # read job posting from --text/--file/stdin
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

    job_text = (job_text or "").strip()[:MAX_JOB_CHARS]
    if not job_text:
        print("Verdict: Fake\nReasons:\n- No job text provided")
        return

    passages, metas = _load_corpus()
    if not passages:
        print("Verdict: Real\nReasons:\n- No corpus found; no strong red flags in text")
        return

    # Vectorize corpus + query
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(passages + [job_text])
    Q = X[-1]            # query vector
    C = X[:-1]           # corpus matrix

    # Retrieve top-k
    sims = cosine_similarity(Q, C).flatten()
    order = sims.argsort()[::-1][:TOP_K]

    # Build tiny class signal using exemplars
    fake_ex, real_ex = _load_exemplar_sets()
    sim_fake = sim_real = 0.0
    if fake_ex and real_ex:
        # vectorize both exemplars with the same vectorizer vocabulary
        ex_docs = [fake_ex, real_ex]
        EX = vec.transform(ex_docs)     # shape (2, V)
        sim_fake = cosine_similarity(Q, EX[0]).item()
        sim_real = cosine_similarity(Q, EX[1]).item()

    # RF/GF counts
    rf_hits, gf_hits = _rf_gf_counts(job_text)

    # ---------- extremely simple scoring ----------
    # combine signals: exemplar tilt + RF/GF counts + top-k similarity tilt
    topk_fake_bias = 0.0
    topk_texts = []
    for i in order:
        topk_texts.append(metas[i])
        # crude hint: if a top chunk came from fake exemplars file name, tilt a bit
        base = metas[i].split("#", 1)[0].lower()
        if "fake_job_exemplars.txt" in base:
            topk_fake_bias += 0.1
        if "real_job_exemplars.txt" in base:
            topk_fake_bias -= 0.1

    score = 0.0
    score += (sim_fake - sim_real)              # positive => fake leaning
    score += 0.5 * len(rf_hits)                 # red flags push to fake
    score -= 0.3 * len(gf_hits)                 # green flags pull to real
    score += topk_fake_bias

    verdict = "Fake" if score > 0 else "Real"

    # --------- print minimal, human-readable output ----------
    print("Verdict:", verdict)
    print("Reasons:")
    # Reason 1: which signals fired
    reasons = []
    if rf_hits:
        reasons.append(f"- Red flags: {', '.join(sorted(set(rf_hits)))}")
    if sim_fake or sim_real:
        reasons.append(f"- Exemplar similarity tilt: fake={sim_fake:.2f}, real={sim_real:.2f}")
    if topk_fake_bias != 0:
        reasons.append(f"- Retrieved chunks bias: {topk_fake_bias:+.2f} (from top-k source names)")
    if gf_hits:
        reasons.append(f"- Green flags: {', '.join(sorted(set(gf_hits)))}")

    if not reasons:
        # default generic reason using top-k
        reasons.append("- Decision based on similarity to retrieved context")

    for r in reasons[:3]:
        print(r)

    # Show which chunks we used (helps debug)
    print("\nTop-K passages:")
    for m in topk_texts:
        print("•", m)

if __name__ == "__main__":
    main()
