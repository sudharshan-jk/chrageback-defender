"""Run agent vs baseline over N disputes. Log every metric to data/results.csv."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import json
import time
import csv

from src.agent.run import run_case
from src.eval.baseline import run_baseline
from src.eval.judge import judge_letter

N_CASES = int(sys.argv[1]) if len(sys.argv) > 1 else 50
JUDGE_EVERY = 5  # judge every Nth case to stay inside free-tier limits


def evidence_summary(case_result) -> str:
    present = ", ".join(case_result.gather.evidence_present) or "none"
    missing = ", ".join(case_result.gather.evidence_missing) or "none"
    return f"present: {present}\nmissing: {missing}"


def main():
    disputes = json.loads(Path("data/disputes.json").read_text(encoding="utf-8"))[:N_CASES]
    rows = []

    print(f"running eval on {len(disputes)} disputes...\n")
    t_start = time.time()

    for i, d in enumerate(disputes):
        truth = d["ground_truth_winnable"]

        # --- agent ---
        try:
            a = run_case(d["notice_text"], order_id=d["order_id"])
            agent_rec = a.recommendation
            agent_triage_correct = (agent_rec == "fight") == truth
            agent_latency = a.latency_ms
            agent_fallback = a.used_fallback
            agent_letter = a.letter_text or ""
            agent_stripped = a.validation.stripped_claims if a.validation else 0
            agent_total_claims = a.validation.total_claims if a.validation else 0
            agent_error = ""
        except Exception as e:
            agent_rec, agent_triage_correct = "error", False
            agent_latency, agent_fallback = 0, True
            agent_letter, agent_stripped, agent_total_claims = "", 0, 0
            agent_error = f"{type(e).__name__}: {e}"
            a = None

        # --- baseline ---
        b = run_baseline(d)
        base_triage_correct = (b.recommendation == "fight") == truth

        # --- judge (sampled) ---
        agent_score = base_score = None
        if i % JUDGE_EVERY == 0 and a is not None:
            summ = evidence_summary(a)
            if agent_letter:
                agent_score = judge_letter(agent_letter, d["reason_code"], d["network"], summ)["total"]
                time.sleep(1)
            base_score = judge_letter(b.letter_text, d["reason_code"], d["network"], summ)["total"]
            time.sleep(1)

        rows.append({
            "dispute_id": d["dispute_id"],
            "reason_code": d["reason_code"],
            "network": d["network"],
            "ground_truth_winnable": truth,
            "agent_recommendation": agent_rec,
            "agent_triage_correct": agent_triage_correct,
            "agent_latency_ms": agent_latency,
            "agent_used_fallback": agent_fallback,
            "agent_claims_stripped": agent_stripped,
            "agent_claims_total": agent_total_claims,
            "agent_letter_score": agent_score if agent_score is not None else "",
            "agent_error": agent_error,
            "baseline_recommendation": b.recommendation,
            "baseline_triage_correct": base_triage_correct,
            "baseline_latency_ms": b.latency_ms,
            "baseline_letter_score": base_score if base_score is not None else "",
        })

        elapsed = time.time() - t_start
        eta = (elapsed / (i + 1)) * (len(disputes) - i - 1)
        mark = "OK" if agent_triage_correct else "MISS"
        print(f"[{i+1}/{len(disputes)}] {d['reason_code']:>6} truth={str(truth):>5} "
              f"agent={agent_rec:>7} {mark}  fb={agent_fallback}  eta={eta/60:.1f}min")

    out = Path("data/results.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {out}")
    print(f"total time: {(time.time() - t_start)/60:.1f} min")


if __name__ == "__main__":
    main()
