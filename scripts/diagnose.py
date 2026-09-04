import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import json
from src.tools.mock_merchant import get_transaction_signals, get_ip_device_history

disputes = json.loads(open("data/disputes.json").read())
d = disputes[1]
oid = d["order_id"]
orders = {o["order_id"]: o for o in json.loads(open("data/mock_orders.json").read())}
o = orders[oid]

print(f"dispute {d['dispute_id']} code {d['reason_code']} truth={d['ground_truth_winnable']}")
print(f"order {oid}")
print(f"_has_evidence flags for 10.4 requirements:")
for ev in ["avs_match_result", "cvv2_match_result", "3ds_authentication_result",
           "device_fingerprint_or_ip_history", "customer_login_and_order_history",
           "delivery_address_matches_billing_address"]:
    print(f"  {ev}: {o['_has_evidence'].get(ev, 'MISSING FROM ORDER')}")

print()
print("get_transaction_signals output:")
print(json.dumps(get_transaction_signals(oid), indent=2))
print()
print("get_ip_device_history output:")
print(json.dumps(get_ip_device_history(o["customer_id"]), indent=2))
