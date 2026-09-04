"""Generate 100 mock orders + 100 disputes for a curated set of reason codes.

We restrict to codes whose required_evidence is majority-gatherable by our
mock tools. This keeps ground truth honest and eval meaningful.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import random
from datetime import datetime, timedelta

from src.agent.gather import EVIDENCE_TO_TOOL

random.seed(42)

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))
GATHERABLE = set(EVIDENCE_TO_TOOL.keys())

# Curated demo codes — the ones our tools genuinely support.
# These cover the main dispute categories a Razorpay merchant would face.
DEMO_CODES = {
    ("mastercard", "4855"),  # goods not provided (6/6 gatherable)
    ("visa", "10.4"),        # fraud, card-absent (6/6 gatherable)
    ("visa", "13.1"),        # merchandise not received (3/5 gatherable)
}

USABLE_CODES = [
    c for c in CORPUS
    if (c["network"].lower(), c["code"]) in DEMO_CODES
]

print(f"[info] curated to {len(USABLE_CODES)} demo codes:", file=sys.stderr)
for c in USABLE_CODES:
    gettable = sum(1 for ev in c["required_evidence"] if ev in GATHERABLE)
    print(f"[info]   {c['network']} {c['code']}: {gettable}/{len(c['required_evidence'])} evidence types gatherable", file=sys.stderr)

if len(USABLE_CODES) < 3:
    raise RuntimeError(f"only {len(USABLE_CODES)} demo codes matched the corpus. Check DEMO_CODES vs reason_codes.json")

FIRST_NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Isha", "Kabir", "Meera",
               "Rohan", "Priya", "Sam", "Emma", "Liam", "Olivia", "Noah", "Ava"]
LAST_NAMES = ["Sharma", "Patel", "Kumar", "Singh", "Reddy", "Iyer", "Nair", "Rao",
              "Smith", "Johnson", "Brown", "Davis"]
CARRIERS = ["BlueDart", "Delhivery", "DHL", "FedEx", "IndiaPost"]
PAYMENT_METHODS = ["card_visa", "card_mastercard", "upi", "netbanking"]


def rand_date(days_ago_min=5, days_ago_max=90):
    return (datetime.now() - timedelta(days=random.randint(days_ago_min, days_ago_max))).isoformat()


def generate_orders(n: int = 100) -> list[dict]:
    all_evidence = sorted({e for c in USABLE_CODES for e in c["required_evidence"]})
    orders = []
    for i in range(n):
        has_evidence = {ev: random.random() < 0.75 for ev in all_evidence}
        orders.append({
            "order_id": f"ord_{1000 + i}",
            "customer_id": f"cus_{100 + i}",
            "customer_name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "amount_inr": round(random.uniform(500, 25000), 2),
            "currency": "INR",
            "payment_method": random.choice(PAYMENT_METHODS),
            "created_at": rand_date(30, 90),
            "carrier": random.choice(CARRIERS),
            "tracking_number": f"TRK{random.randint(10**9, 10**10 - 1)}",
            "delivered_at": rand_date(5, 25),
            "billing_address_matches_shipping": random.random() < 0.85,
            "prior_chargebacks_for_customer": random.choices([0, 1, 2, 3], weights=[70, 20, 7, 3])[0],
            "avs_result": random.choice(["FULL_MATCH", "PARTIAL_MATCH", "NO_MATCH", "NOT_CHECKED"]),
            "cvv2_result": random.choice(["MATCH", "NO_MATCH", "NOT_CHECKED"]),
            "three_ds_result": random.choice(["AUTHENTICATED", "ATTEMPTED", "NOT_AUTHENTICATED", "NOT_APPLICABLE"]),
            "ip_country": random.choice(["IN", "IN", "IN", "US", "GB", "AE"]),
            "device_fingerprint": f"dev_{random.randint(10000, 99999)}",
            "_has_evidence": has_evidence,
        })
    return orders


def generate_disputes(orders: list[dict], n: int = 100) -> list[dict]:
    disputes = []
    for i in range(n):
        oid = random.choice(orders)["order_id"]
        order = next(o for o in orders if o["order_id"] == oid)
        code_entry = random.choice(USABLE_CODES)

        required = code_entry["required_evidence"]
        gatherable_required = [ev for ev in required if ev in GATHERABLE]
        # Winnable iff every gatherable required evidence is present
        winnable = (
            len(gatherable_required) >= 1
            and all(order["_has_evidence"].get(ev, False) for ev in gatherable_required)
        )

        dispute_id = f"disp_{2000 + i}"
        notice_text = (
            f"CHARGEBACK NOTICE\n"
            f"Dispute ID: {dispute_id}\n"
            f"Transaction ID: txn_{oid.replace('ord_', '')}\n"
            f"Order ID: {oid}\n"
            f"Amount: INR {order['amount_inr']:.2f}\n"
            f"Cardholder: {order['customer_name']}\n"
            f"Network: {code_entry['network'].upper()}\n"
            f"Reason Code: {code_entry['code']}\n"
            f"Reason: {code_entry['title']}\n"
            f"Description: {code_entry['short_description']}\n"
            f"Response deadline: {code_entry['deadline_days']} days from {rand_date(1, 3)[:10]}"
        )
        disputes.append({
            "dispute_id": dispute_id,
            "order_id": oid,
            "network": code_entry["network"],
            "reason_code": code_entry["code"],
            "notice_text": notice_text,
            "ground_truth_winnable": winnable,
        })
    return disputes


if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    orders = generate_orders(100)
    disputes = generate_disputes(orders, 100)
    Path("data/mock_orders.json").write_text(json.dumps(orders, indent=2), encoding="utf-8")
    Path("data/disputes.json").write_text(json.dumps(disputes, indent=2), encoding="utf-8")
    win = sum(1 for d in disputes if d["ground_truth_winnable"])
    print(f"generated {len(orders)} orders")
    print(f"generated {len(disputes)} disputes ({win} winnable, {len(disputes) - win} not)")
    print(f"reason codes in use: {len({d['reason_code'] for d in disputes})}")


