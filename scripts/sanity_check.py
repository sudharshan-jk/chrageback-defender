import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
from src.agent.classify import classify
from src.agent.gather import gather

disputes = json.loads(open("data/disputes.json").read())
correct = 0
for i in range(10):
    d = disputes[i]
    cls = classify(d["notice_text"])
    result = gather(cls, order_id=d["order_id"])
    agent_says_win = result.recommendation == "fight"
    match = agent_says_win == d["ground_truth_winnable"]
    correct += match
    marker = "OK" if match else "MISS"
    print(f"#{i} {d['reason_code']:>6} truth={str(d['ground_truth_winnable']):>5} agent={result.recommendation:>7} win={result.winnability:.2f}  {marker}")
print(f"\nagreement: {correct}/10")

