#!/usr/bin/env python3
# rag_single_simple.py — minimal, fast, no-LLM "RAG"
# - Loads ./data/*.txt
# - Chunks + TF-IDF (1–2 grams, sublinear TF, min_df=2) and retrieves TOP_K
# - Scores with: exemplar similarity (fake - real) + red/green flag counts + tiny heuristics
# - Prints:
#     Verdict: Real|Fake
#     Reasons:
#     - ...
#     - ...
#     - ...

import sys, os, re, glob
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------- Config (override with env) --------
DATA_DIR        = Path("data")
TOP_K           = int(os.environ.get("RAG_TOPK", "6"))       # retrieval breadth
CHUNK_SIZE      = int(os.environ.get("RAG_CHUNK", "450"))    # smaller chunks improve recall
CHUNK_OVERLAP   = int(os.environ.get("RAG_OVERLAP", "90"))
MAX_JOB_CHARS   = int(os.environ.get("RAG_JOB_CHARS", "1500"))
SHOW_TOPK       = bool(int(os.environ.get("RAG_SHOW_TOPK", "1")))  # 1: print chunk names at end

# Tiny keyword nudges (cheap heuristics)
WATCH_TERMS = [
    "signing bonus", "onboarding bonus", "gift card", "crypto", "google form",
    "telegram", "whatsapp", "cash app", "venmo"
]
ATS_WHITELIST = r"\b(workday|greenhouse|lever|smartrecruiters)\b"

# -------- Small helpers --------
def _read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    out, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        out.append(text[i:i+size])
        i += step
    return out

def _load_corpus() -> Tuple[List[str], List[str]]:
    """Return passages and metadata labels from ./data/*.txt."""
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

# -------- Cheap signals (regex) --------
RF_PATTERNS = [
    ("RF-04", r"\b(no interview|required today|instant hire|start immediately|telegram|whatsapp)\b"),
    ("RF-05", r"\b(ssn|social security|bank account|routing number|passport|id scan|remote desktop)\b"),
    ("RF-03", r"\$\s?\d{2,},?\d{0,3}\s*(?:/|per)?\s?(?:hour|hr)\b.*\bno experience\b"),
]
GF_PATTERNS = [
    ("GF-04", ATS_WHITELIST),
    ("GF-02", r"\bresponsibilities\b.*\brequirements\b"),
    ("GF-09", r"\bequal opportunity employer\b|\beeo\b"),
]

def _rf_gf_counts(job_text: str):
    t = job_text.lower()
    rf = [code for code, pat in RF_PATTERNS if re.search(pat, t)]
    gf = [code for code, pat in GF_PATTERNS if re.search(pat, t, re.I)]
    return rf, gf

# -------- Exemplars (optional but helpful) --------
def _load_exemplar_sets():
    fake_fp = DATA_DIR / "fake_job_exemplars.txt"
    real_fp = DATA_DIR / "real_job_exemplars.txt"
    fake_txt = _read_txt(fake_fp) if fake_fp.exists() else ""
    real_txt = _read_txt(real_fp) if real_fp.exists() else ""
    return fake_txt.strip(), real_txt.strip()

# -------- Main simple RAG --------
def main():
    # Read job posting from --text / --file / stdin
    args = sys.argv[1:]
    job_text = ""
    if "--text" in args:
        i = args.index("--text")
        if i + 1 < len(args):
            job_text = args[i + 1]
    elif "--file" in args:
        i = args.index("--file")
        if i + 1 < len(args):
            job_text = Path(args[i + 1]).read_text(encoding="utf-8", errors="ignore")
    else:
        job_text = sys.stdin.read()

    # Clean & trim
    job_text = (job_text or "")
    q = re.sub(r'https?://\S+|www\.\S+|[\w\.-]+@[\w\.-]+', ' ', job_text)
    q = re.sub(r'\s+', ' ', q).strip()[:MAX_JOB_CHARS]
    if not q:
        print("Verdict: Fake\nReasons:\n- No job text provided")
        return

    passages, metas = _load_corpus()
    if not passages:
        # With no corpus, be conservative but not overly fake-happy
        rf_hits, gf_hits = _rf_gf_counts(q)
        if "RF-05" in rf_hits or ("RF-04" in rf_hits and len(rf_hits) >= 2):
            print("Verdict: Fake\nReasons:\n- Strong red flags: " + ", ".join(sorted(set(rf_hits))))
        else:
            print("Verdict: Real\nReasons:\n- No corpus found and no strong red flags detected")
        return

    # Vectorizer: word 1–2 grams, sublinear TF, ignore singleton noise
    vec = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.95,
    )
    X = vec.fit_transform(passages + [q])
    Q = X[-1]   # query
    C = X[:-1]  # corpus
    sims = cosine_similarity(Q, C).flatten()
    order = sims.argsort()[::-1][:TOP_K]

    # Exemplar similarity tilt
    fake_ex, real_ex = _load_exemplar_sets()
    sim_fake = sim_real = 0.0
    if fake_ex and real_ex:
        EX = vec.transform([fake_ex, real_ex])
        sim_fake = float(cosine_similarity(Q, EX[0]))
        sim_real = float(cosine_similarity(Q, EX[1]))

    # RF / GF counts
    rf_hits, gf_hits = _rf_gf_counts(q)

    # Retrieved-chunk source bias (very tiny)
    topk_bias = 0.0
    topk_names = []
    for i in order:
        meta = metas[i]
        topk_names.append(meta)
        base = meta.split("#", 1)[0].lower()
        if "fake_job_exemplars.txt" in base: topk_bias += 0.10
        if "real_job_exemplars.txt" in base: topk_bias -= 0.10

    # Watch-terms micro-signal
    hits = sum(1 for w in WATCH_TERMS if w in q.lower())
    watch_bonus = 0.05 * hits

    # ATS whitelist helps legit
    ats_bonus = -0.20 if re.search(ATS_WHITELIST, q, re.I) else 0.0

    # Short posts are suspicious
    short_bump = 0.15 if len(q) < 120 else 0.0

    # ---------- Simple score (keep tiny & interpretable) ----------
    score  = (sim_fake - sim_real)        # exemplar tilt ( + => fake )
    score += 0.40 * len(rf_hits)          # red flags push to fake
    score -= 0.35 * len(gf_hits)          # green flags pull to real
    score += topk_bias                    # tiny bias from retrieved names
    score += watch_bonus                  # tiny scam terms
    score += short_bump                   # very short text bump toward fake
    score += ats_bonus                    # ATS presence pulls toward real

    # Slight margin needed to call Fake
    verdict = "Fake" if score > 0.15 else "Real"

    # ---------- Human-friendly reasons ----------
    reasons = []
    if rf_hits:
        reasons.append(f"- Red flags: {', '.join(sorted(set(rf_hits)))}")
    if re.search(ATS_WHITELIST, q, re.I):
        reasons.append("- ATS platform mentioned (Workday/Lever/Greenhouse/SmartRecruiters)")
    if sim_fake or sim_real:
        reasons.append(f"- Exemplar similarity tilt: fake={sim_fake:.2f}, real={sim_real:.2f}")
    if hits:
        reasons.append(f"- Risk terms present: {hits} hit(s)")
    if len(q) < 120:
        reasons.append("- Very short posting text")
    if not reasons:
        reasons.append("- Decision based on similarity to retrieved context and simple rules")

    print("Verdict:", verdict)
    print("Reasons:")
    for r in reasons[:3]:
        print(r)

    if SHOW_TOPK:
        print("\nTop-K passages:")
        for m in topk_names:
            print("•", m)

if __name__ == "__main__":
    main()
