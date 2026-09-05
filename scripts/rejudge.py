import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import json, time
import pandas as pd

from src.agent.run import run_case
from src.eval.baseline import run_baseline
from src.eval.judge import judge_letter

N = 6  # judge this many cases
disputes = json.loads(Path("data/disputes.json").read_text(encoding="utf-8"))
df = pd.read_csv("data/results.csv")

# Pick cases spread across the run
idxs = [0, 10, 20, 30, 40, 45][:N]

for i in idxs:
    d = disputes[i]
    print(f"judging case {i} ({d['reason_code']})...")
    a = run_case(d["notice_text"], order_id=d["order_id"])
    b = run_baseline(d)
    summ = f"present: {', '.join(a.gather.evidence_present) or 'none'}\nmissing: {', '.join(a.gather.evidence_missing) or 'none'}"

    if a.letter_text:
        s = judge_letter(a.letter_text, d["reason_code"], d["network"], summ)
        df.loc[i, "agent_letter_score"] = s["total"]
        print(f"  agent:    {s['total']:.2f}  ({s.get('note','')[:70]})")
        time.sleep(8)
    else:
        print("  agent:    (no letter — recommended accept)")

    s = judge_letter(b.letter_text, d["reason_code"], d["network"], summ)
    df.loc[i, "baseline_letter_score"] = s["total"]
    print(f"  baseline: {s['total']:.2f}")
    time.sleep(8)

df.to_csv("data/results.csv", index=False)
print("\nupdated data/results.csv")
