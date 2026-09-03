"""Generate 100 mock orders + 100 disputes with hidden ground truth.

An order's "evidence completeness" determines whether the dispute is winnable:
- If all required_evidence for the dispute's reason code is present, ground_truth_winnable=True
- Otherwise False

This gives us a deterministic ground truth to evaluate triage accuracy.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # reproducible

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))

# Only use codes with at least 3 required-evidence items (skip thin entries)
USABLE_CODES = [c for c in CORPUS if len(c.get("required_evidence", [])) >= 3]

# Master list of every evidence type across the corpus
ALL_EVIDENCE_TYPES = sorted({e for c in USABLE_CODES for e in c["required_evidence"]})

FIRST_NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Isha", "Kabir", "Meera",
               "Rohan", "Priya", "Sam", "Emma", "Liam", "Olivia", "Noah", "Ava"]
LAST_NAMES = ["Sharma", "Patel", "Kumar", "Singh", "Reddy", "Iyer", "Nair", "Rao",
              "Smith", "Johnson", "Brown", "Davis"]
CARRIERS = ["BlueDart", "Delhivery", "DHL", "FedEx", "IndiaPost"]
PAYMENT_METHODS = ["card_visa", "card_mastercard", "upi", "netbanking"]


def rand_date(days_ago_min=5, days_ago_max=90):
    return (datetime.now() - timedelta(days=random.randint(days_ago_min, days_ago_max))).isoformat()


def generate_orders(n: int = 100) -> list[dict]:
    orders = []
    for i in range(n):
        oid = f"ord_{1000 + i}"
        customer_id = f"cus_{100 + i}"
        # Randomly decide which evidence types this order has
        # Higher probability = more complete orders
        has_evidence = {
            ev: random.random() < 0.80  # each evidence type has 65% chance of being present
            for ev in ALL_EVIDENCE_TYPES
        }
        orders.append({
            "order_id": oid,
            "customer_id": customer_id,
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
            "ip_country": random.choice(["IN", "IN", "IN", "US", "GB", "AE"]),  # weighted to India
            "device_fingerprint": f"dev_{random.randint(10000, 99999)}",
            "_has_evidence": has_evidence,  # hidden field, used to compute ground truth
        })
    return orders


def generate_disputes(orders: list[dict], n: int = 100) -> list[dict]:
    disputes = []
    for i in range(n):
        oid = random.choice(orders)["order_id"]
        order = next(o for o in orders if o["order_id"] == oid)
        code_entry = random.choice(USABLE_CODES)

        # Ground truth: winnable iff every required evidence type is present in the order
        required = code_entry["required_evidence"]
        winnable = all(order["_has_evidence"].get(ev, False) for ev in required)

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
            "ground_truth_winnable": winnable,  # hidden from agent, used in eval
        })
    return disputes


if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)

    orders = generate_orders(100)
    disputes = generate_disputes(orders, 100)

    Path("data/mock_orders.json").write_text(json.dumps(orders, indent=2), encoding="utf-8")
    Path("data/disputes.json").write_text(json.dumps(disputes, indent=2), encoding="utf-8")

    winnable_count = sum(1 for d in disputes if d["ground_truth_winnable"])
    print(f"generated {len(orders)} orders")
    print(f"generated {len(disputes)} disputes ({winnable_count} winnable, {len(disputes) - winnable_count} not)")
