#!/usr/bin/env python3
# eval_wrapper.py — compares your RAG (rag_single.py) vs base Mistral (no RAG)
# Outputs confusion matrices + accuracy bar. Also supports single-text quick check.

import os, sys, re, json, argparse, subprocess
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, accuracy_score

RAG_PROG       = "rag_single.py"
OLLAMA_URL     = "http://localhost:11434/api/generate"
MISTRAL_MODEL  = "mistral:7b"      # `ollama pull mistral:7b`
TIMEOUT_SEC    = 90
LABELS         = [0,1,2]           # 0=Real, 1=Fake, 2=Unknown
LABEL_NAMES    = ["Real","Fake","Unknown"]

def _parse_verdict(text: str) -> int:
    """Parse 'Verdict: Real|Fake|Uncertain' (case-insensitive) to {0,1,2}, tolerant of markdown."""
    if not text:
        return 2
    t = text.strip()
    # remove simple markdown/HTML noise and normalize spaces
    t = re.sub(r"\*\*|__", "", t)                  # strip **bold** and __underline__
    t = re.sub(r"</?[^>]+>", "", t)                # strip simple HTML tags if any
    t = re.sub(r"[ \t]+", " ", t)                  # collapse spaces
    # match on its own line, anywhere
    m = re.search(r"(?im)^\s*verdict:\s*(real|fake|uncertain)\b", t)
    if not m:
        return 2
    v = m.group(1).lower()
    return 0 if v == "real" else 1 if v == "fake" else 2

def run_rag(job_text: str) -> tuple[int, str]:
    """Call rag_single.py and parse plain-text verdict."""
    try:
        p = subprocess.run(
            [sys.executable, RAG_PROG, "--text", job_text],
            capture_output=True, text=True, timeout=TIMEOUT_SEC
        )
        out = (p.stdout or "") + (("\n"+p.stderr) if p.stderr else "")
        return _parse_verdict(out), out
    except Exception as e:
        return 2, f"[RAG error] {e}"

def run_mistral_plain(job_text: str) -> tuple[int, str]:
    """Call Mistral via Ollama CLI (no RAG). Same output rules as RAG."""
    prompt = f"""You are a careful reviewer for job posting fraud.
Use the JOB POSTING directly for evidence. If signals are weak or contradictory, return Uncertain.

STRICT OUTPUT RULES:
- No markdown.
- Print exactly two sections: 'Verdict:' then 'Reasons:' with 1-3 bullets.
- Verdict must be exactly one of: Real, Fake, Uncertain.

JOB POSTING:
{job_text}

Return EXACTLY this:

Verdict: Real|Fake|Uncertain
Reasons:
- short reason #1
- short reason #2
- short reason #3 (optional)
"""
    try:
        p = subprocess.run(
            ["ollama", "run", MISTRAL_MODEL],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SEC
        )
        out = (p.stdout or "") + (("\n"+p.stderr) if p.stderr else "")
        return _parse_verdict(out), out
    except Exception as e:
        return 2, f"[Mistral error] {e}"

def _combine_text_row(row: pd.Series) -> str:
    parts = []
    for col, val in row.items():
        if pd.isna(val): continue
        s = str(val)
        if len(s) < 3: continue
        parts.append(s)
    return "\n".join(parts)[:2000]

def load_dataset(path: str) -> tuple[pd.DataFrame, str]:
    """Auto-detect label col (0/1[/2]) and make a combined text column."""
    df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
    label_col = None
    for c in df.columns[::-1]:
        try:
            vals = pd.to_numeric(df[c], errors="coerce").dropna().unique().tolist()
            if set(vals).issubset({0,1,2}) and len(vals) > 0:
                label_col = c; break
        except Exception:
            pass
    if label_col is None:
        label_col = df.columns[-1]
    df["__text__"]  = df.apply(_combine_text_row, axis=1)
    df["__label__"] = pd.to_numeric(df[label_col], errors="coerce").fillna(2).astype(int)
    return df[["__text__","__label__"]], label_col

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

def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", type=str, help="Single job posting text")
    mode.add_argument("--file", type=str, help="Single job posting text file")
    mode.add_argument("--dataset", type=str, help="CSV for batch eval (pare_post.csv or new_set.csv)")
    ap.add_argument("--max", type=int, default=20, help="Max rows for batch eval")
    args = ap.parse_args()

    # Single quick compare (no plots, prints both verdicts)
    if args.text or args.file:
        job_text = args.text if args.text else Path(args.file).read_text(encoding="utf-8", errors="ignore")
        job_text = job_text.strip()
        if not job_text:
            print("Empty input."); sys.exit(1)
        rag_label, rag_raw = run_rag(job_text)
        mis_label, mis_raw = run_mistral_plain(job_text)

        def _label_name(i): return LABEL_NAMES[i] if i in (0,1,2) else "Unknown"
        print("RAG Output:\n" + rag_raw.strip())
        print("\nMistral (no RAG) Output:\n" + mis_raw.strip())
        print(f"\nParsed Verdicts → RAG: {_label_name(rag_label)} | Mistral: {_label_name(mis_label)}")
        sys.exit(0)

    # Batch eval (plots + CSV)
    df, label_col = load_dataset(args.dataset)
    if args.max: df = df.head(args.max)
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
