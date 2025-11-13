#!/usr/bin/env python3
# rag_single_simple.py — minimal, fast, no-LLM "RAG"
# Printing rewritten for natural explanations

import sys, os, re, glob
from pathlib import Path
from typing import List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR        = Path("data")
TOP_K           = int(os.environ.get("RAG_TOPK", "6"))
CHUNK_SIZE      = int(os.environ.get("RAG_CHUNK", "450"))
CHUNK_OVERLAP   = int(os.environ.get("RAG_OVERLAP", "90"))
MAX_JOB_CHARS   = int(os.environ.get("RAG_JOB_CHARS", "1500"))
SHOW_TOPK       = bool(int(os.environ.get("RAG_SHOW_TOPK", "1")))

WATCH_TERMS = [
    "signing bonus", "onboarding bonus", "gift card", "crypto", "google form",
    "telegram", "whatsapp", "cash app", "venmo"
]
ATS_WHITELIST = r"\b(workday|greenhouse|lever|smartrecruiters)\b"

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

def _load_exemplar_sets():
    fake_fp = DATA_DIR / "fake_job_exemplars.txt"
    real_fp = DATA_DIR / "real_job_exemplars.txt"
    fake_txt = _read_txt(fake_fp) if fake_fp.exists() else ""
    real_txt = _read_txt(real_fp) if real_fp.exists() else ""
    return fake_txt.strip(), real_txt.strip()

def main():
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

    job_text = (job_text or "")
    q = re.sub(r'https?://\S+|www\.\S+|[\w\.-]+@[\w\.-]+', ' ', job_text)
    q = re.sub(r'\s+', ' ', q).strip()[:MAX_JOB_CHARS]
    if not q:
        print("Verdict: Fake")
        print("Reasons:\n- The text is empty, which makes it impossible to assess authenticity.")
        return

    passages, metas = _load_corpus()
    if not passages:
        rf_hits, gf_hits = _rf_gf_counts(q)
        if "RF-05" in rf_hits or ("RF-04" in rf_hits and len(rf_hits) >= 2):
            print("Verdict: Fake")
            print("Reasons:\n- The job description includes obvious scam indicators such as requests for personal information or instant hiring promises.")
        else:
            print("Verdict: Real")
            print("Reasons:\n- The posting doesn’t show any classic scam signs, such as requests for money or personal data.")
        return

    vec = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.95,
    )
    X = vec.fit_transform(passages + [q])
    Q = X[-1]
    C = X[:-1]
    sims = cosine_similarity(Q, C).flatten()
    order = sims.argsort()[::-1][:TOP_K]

    fake_ex, real_ex = _load_exemplar_sets()
    sim_fake = sim_real = 0.0
    if fake_ex and real_ex:
        EX = vec.transform([fake_ex, real_ex])
        sim_fake = float(cosine_similarity(Q, EX[0]))
        sim_real = float(cosine_similarity(Q, EX[1]))

    rf_hits, gf_hits = _rf_gf_counts(q)

    topk_bias = 0.0
    topk_names = []
    for i in order:
        meta = metas[i]
        topk_names.append(meta)
        base = meta.split("#", 1)[0].lower()
        if "fake_job_exemplars.txt" in base: topk_bias += 0.10
        if "real_job_exemplars.txt" in base: topk_bias -= 0.10

    hits = sum(1 for w in WATCH_TERMS if w in q.lower())
    watch_bonus = 0.05 * hits
    ats_bonus = -0.20 if re.search(ATS_WHITELIST, q, re.I) else 0.0
    short_bump = 0.15 if len(q) < 120 else 0.0

    score  = (sim_fake - sim_real)
    score += 0.40 * len(rf_hits)
    score -= 0.35 * len(gf_hits)
    score += topk_bias
    score += watch_bonus
    score += short_bump
    score += ats_bonus

    verdict = "Fake" if score > 0.15 else "Real"

    # ----- human explanations -----
    print("Verdict:", verdict)
    print("Reasons:")
    if verdict == "Fake":
        if "RF-05" in rf_hits:
            print("- It asks for sensitive personal or financial details (like SSN or bank info).")
        if len(q) < 120:
            print("- The post is unusually short, which is typical of copy-paste scam ads.")
        if hits:
            print("- It contains suspicious terms (e.g., crypto, gift cards, or instant bonuses).")
        if re.search(r"telegram|whatsapp", q, re.I):
            print("- It references messaging apps often used by scammers (Telegram, WhatsApp).")
        if sim_fake > sim_real:
            print("- Its phrasing resembles previously known fake job exemplars.")
        if not (rf_hits or hits):
            print("- It lacks specific company or job details, which often signals inauthenticity.")
    else:
        if re.search(ATS_WHITELIST, q, re.I):
            print("- It mentions a legitimate applicant-tracking system (like Workday or Lever).")
        if gf_hits:
            print("- It includes standard professional sections such as ‘Responsibilities’ and ‘Requirements’.")
        if sim_real >= sim_fake:
            print("- Its writing style is closer to genuine job descriptions than scam exemplars.")
        if not (gf_hits or re.search(ATS_WHITELIST, q, re.I)):
            print("- It provides enough structured information to appear legitimate.")

    if SHOW_TOPK:
        print("\nTop-K supporting passages used:")
        for m in topk_names:
            print("•", m)

if __name__ == "__main__":
    main()
