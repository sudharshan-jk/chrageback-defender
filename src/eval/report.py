"""Summarise data/results.csv into a table + chart."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    df = pd.read_csv("data/results.csv")
    n = len(df)

    agent_acc = df["agent_triage_correct"].mean() * 100
    base_acc = df["baseline_triage_correct"].mean() * 100

    agent_scores = pd.to_numeric(df["agent_letter_score"], errors="coerce").dropna()
    base_scores = pd.to_numeric(df["baseline_letter_score"], errors="coerce").dropna()
    agent_quality = agent_scores.mean() if len(agent_scores) else 0
    base_quality = base_scores.mean() if len(base_scores) else 0

    fallback_rate = df["agent_used_fallback"].mean() * 100
    p50 = df["agent_latency_ms"].median()
    p95 = df["agent_latency_ms"].quantile(0.95)

    total_claims = df["agent_claims_total"].sum()
    stripped = df["agent_claims_stripped"].sum()
    strip_rate = (stripped / total_claims * 100) if total_claims else 0

    accepted = (df["agent_recommendation"] == "accept").sum()
    smart_calls_saved = accepted / n * 100

    print(f"\n{'='*62}")
    print(f"  ChargebackDefender eval — {n} disputes")
    print(f"{'='*62}")
    print(f"{'Metric':<38}{'Baseline':>11}{'Agent':>13}")
    print(f"{'-'*62}")
    print(f"{'Triage accuracy (%)':<38}{base_acc:>11.1f}{agent_acc:>13.1f}")
    print(f"{'Letter quality (0-10, LLM judge)':<38}{base_quality:>11.2f}{agent_quality:>13.2f}")
    print(f"{'Median latency (ms)':<38}{'~0':>11}{p50:>13.0f}")
    print(f"{'-'*62}")
    print(f"{'Fallback rate (%)':<38}{'':>11}{fallback_rate:>13.1f}")
    print(f"{'Claims stripped by validation (%)':<38}{'':>11}{strip_rate:>13.1f}")
    print(f"{'Smart-model calls avoided by triage (%)':<38}{'':>11}{smart_calls_saved:>13.1f}")
    print(f"{'p95 latency (ms)':<38}{'':>11}{p95:>13.0f}")
    print(f"{'='*62}\n")

    # Chart
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    axes[0].bar(["Baseline", "Agent"], [base_acc, agent_acc],
                color=["#94a3b8", "#2563eb"])
    axes[0].set_ylabel("Triage accuracy (%)")
    axes[0].set_title("Fight-vs-accept decision accuracy")
    axes[0].set_ylim(0, 100)
    for i, v in enumerate([base_acc, agent_acc]):
        axes[0].text(i, v + 2, f"{v:.1f}%", ha="center", fontweight="bold")

    axes[1].bar(["Baseline", "Agent"], [base_quality, agent_quality],
                color=["#94a3b8", "#2563eb"])
    axes[1].set_ylabel("Letter quality (0-10)")
    axes[1].set_title("Letter quality (Gemini judge)")
    axes[1].set_ylim(0, 10)
    for i, v in enumerate([base_quality, agent_quality]):
        axes[1].text(i, v + 0.2, f"{v:.2f}", ha="center", fontweight="bold")

    fig.suptitle(f"ChargebackDefender vs template baseline ({n} disputes)", fontweight="bold")
    fig.tight_layout()
    fig.savefig("data/lift_chart.png", dpi=150)
    print("chart written to data/lift_chart.png\n")


if __name__ == "__main__":
    main()
