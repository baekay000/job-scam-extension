#!/usr/bin/env python3
# eval_wrapper.py — compare your RAG (rag_single_llm_simple.py) vs base Mistral (no RAG)
# - Batch mode over CSV: saves confusion matrices + accuracy bar + evaluation_results.csv
# - Single-text mode: prints both raw outputs + parsed verdicts

import os, sys, re, json, argparse, subprocess
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, accuracy_score

# ---------- Config ----------
RAG_PROG       = os.environ.get("RAG_PROG", "rag_single_llm_simple.py")  # set to your RAG filename
MISTRAL_MODEL  = os.environ.get("MISTRAL_MODEL", "mistral:7b")           # `ollama pull mistral:7b`
TIMEOUT_SEC    = int(os.environ.get("EVAL_TIMEOUT", "180"))              # allow for first-load
RETRY_WARMUP   = int(os.environ.get("EVAL_RETRY_WARMUP", "1"))           # 1 = try a warmup if first call fails
LABELS         = [0, 1, 2]                                               # 0=Real, 1=Fake, 2=Unknown
LABEL_NAMES    = ["Real", "Fake", "Unknown"]

# ---------- Parsers ----------
def _parse_verdict(text: str) -> int:
    """
    Accepts:
      Verdict: Real|Fake|Uncertain
    (case-insensitive; tolerates markdown/HTML noise)
    Returns 0/1/2.
    """
    if not text:
        return 2
    t = text.strip()
    t = re.sub(r"\*\*|__", "", t)             # strip bold/underline
    t = re.sub(r"</?[^>]+>", "", t)           # strip simple HTML tags
    t = re.sub(r"[ \t]+", " ", t)
    m = re.search(r"(?im)^\s*verdict:\s*(real|fake|uncertain)\b", t)
    if not m:
        # gentle fallback: if it says fake but not real → Fake; real but not fake → Real; else Unknown
        low = t.lower()
        if "fake" in low and "real" not in low:
            return 1
        if "real" in low and "fake" not in low:
            return 0
        return 2
    v = m.group(1).lower()
    return 0 if v == "real" else 1 if v == "fake" else 2

# ---------- Executors ----------
def run_rag(job_text: str) -> tuple[int, str]:
    """Call your RAG script and parse 'Verdict:'."""
    try:
        p = subprocess.run(
            [sys.executable, RAG_PROG, "--text", job_text],
            capture_output=True, text=True, timeout=TIMEOUT_SEC
        )
        out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
        return _parse_verdict(out), out
    except Exception as e:
        return 2, f"[RAG error] {e}"

def run_mistral_plain(job_text: str) -> tuple[int, str]:
    """
    Call base Mistral via Ollama CLI (no RAG).
    Output format mirrors the RAG script to keep parsing identical.
    Warm-up retry helps on first model load.
    """
    prompt = f"""You are reviewing a job posting for authenticity.
Use ONLY the job text. Be decisive; if evidence is contradictory, choose the better-supported label.

Return EXACTLY this format (no markdown, no extra text):
Verdict: Real|Fake|Uncertain
Reasons:
- short reason #1
- short reason #2 (optional)
- short reason #3 (optional)

JOB POSTING:
{job_text}
""".strip()

    cmd = ["ollama", "run", MISTRAL_MODEL]
    tries = 1 + max(0, RETRY_WARMUP)
    last_err = ""
    for _ in range(tries):
        try:
            p = subprocess.run(
                cmd, input=prompt, text=True, capture_output=True, timeout=TIMEOUT_SEC
            )
            out = (p.stdout or "").strip()
            if out:
                return _parse_verdict(out), out
            last_err = (p.stderr or "").strip()
        except subprocess.TimeoutExpired:
            last_err = f"timeout after {TIMEOUT_SEC}s"

        # warm up model before retry
        try:
            subprocess.run(["ollama", "run", MISTRAL_MODEL, "ok"], text=True, capture_output=True, timeout=30)
        except Exception:
            pass

    return 2, f"[Mistral error] {last_err or 'no output'}"

# ---------- CSV utils ----------
def _combine_text_row(row: pd.Series) -> str:
    parts = []
    for _, val in row.items():
        if pd.isna(val): 
            continue
        s = str(val)
        if len(s) < 3: 
            continue
        parts.append(s)
    return "\n".join(parts)[:2000]

def load_dataset(path: str) -> tuple[pd.DataFrame, str]:
    """
    Heuristically detect a label column with {0,1[,2]} and build a combined text column.
    Returns df[[__text__, __label__]], label_col_name
    """
    df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
    label_col = None
    for c in df.columns[::-1]:
        try:
            vals = pd.to_numeric(df[c], errors="coerce").dropna().unique().tolist()
            if set(vals).issubset({0,1,2}) and len(vals) > 0:
                label_col = c
                break
        except Exception:
            pass
    if label_col is None:
        label_col = df.columns[-1]
    df["__text__"]  = df.apply(_combine_text_row, axis=1)
    df["__label__"] = pd.to_numeric(df[label_col], errors="coerce").fillna(2).astype(int)
    return df[["__text__", "__label__"]], label_col

# ---------- Plots ----------
def plot_results(y_true, y_rag, y_mis):
    acc_rag = accuracy_score(y_true, y_rag)
    acc_mis = accuracy_score(y_true, y_mis)

    cm_rag = confusion_matrix(y_true, y_rag, labels=LABELS)
    cm_mis = confusion_matrix(y_true, y_mis, labels=LABELS)

    plt.figure(figsize=(4.5,4))
    ConfusionMatrixDisplay(cm_rag, display_labels=LABEL_NAMES).plot(values_format="d")
    plt.title("Confusion Matrix — RAG")
    plt.tight_layout(); plt.savefig("cm_rag.png", dpi=160)

    plt.figure(figsize=(4.5,4))
    ConfusionMatrixDisplay(cm_mis, display_labels=LABEL_NAMES).plot(values_format="d")
    plt.title("Confusion Matrix — Mistral (no RAG)")
    plt.tight_layout(); plt.savefig("cm_mistral.png", dpi=160)

    plt.figure(figsize=(5,4))
    plt.bar(["RAG","Mistral"], [acc_rag, acc_mis])
    plt.ylabel("Accuracy")
    plt.title("Model Performance: Accuracy")
    plt.ylim(0,1); plt.tight_layout(); plt.savefig("rag_vs_mistral_accuracy.png", dpi=160)

    return acc_rag, acc_mis

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", type=str, help="Single job posting text")
    mode.add_argument("--file", type=str, help="Single job posting text file")
    mode.add_argument("--dataset", type=str, help="CSV for batch eval (pare_post.csv or new_set.csv)")
    ap.add_argument("--max", type=int, default=20, help="Max rows for batch eval")
    args = ap.parse_args()

    # Single-text quick compare
    if args.text or args.file:
        job_text = args.text if args.text else Path(args.file).read_text(encoding="utf-8", errors="ignore")
        job_text = job_text.strip()
        if not job_text:
            print("Empty input."); sys.exit(1)
        rag_label, rag_raw = run_rag(job_text)
        mis_label, mis_raw = run_mistral_plain(job_text)

        def _name(i): return LABEL_NAMES[i] if i in (0,1,2) else "Unknown"
        print("RAG Output:\n" + rag_raw.strip())
        print("\nMistral (no RAG) Output:\n" + mis_raw.strip())
        print(f"\nParsed Verdicts → RAG: {_name(rag_label)} | Mistral: {_name(mis_label)}")
        sys.exit(0)

    # Batch eval
    df, label_col = load_dataset(args.dataset)
    if args.max:
        df = df.head(args.max)
    print(f"Evaluating {len(df)} samples from '{args.dataset}' (label column: '{label_col}')")

    y_true = df["__label__"].tolist()
    rag_preds, mis_preds = [], []

    for idx, row in df.iterrows():
        text = str(row["__text__"])[:2000]
        r_label, _ = run_rag(text)
        m_label, _ = run_mistral_plain(text)
        rag_preds.append(r_label); mis_preds.append(m_label)
        print(f"[{len(rag_preds):02d}/{len(df)}] true={row['__label__']} rag={r_label} mis={m_label}")

    pd.DataFrame({
        "true": y_true, "rag_pred": rag_preds, "mistral_pred": mis_preds
    }).to_csv("evaluation_results.csv", index=False)

    acc_rag, acc_mis = plot_results(y_true, rag_preds, mis_preds)
    print("\nSaved: evaluation_results.csv, cm_rag.png, cm_mistral.png, rag_vs_mistral_accuracy.png")
    print(f"Accuracy — RAG: {acc_rag:.3f} | Mistral: {acc_mis:.3f}")

if __name__ == "__main__":
    main()
