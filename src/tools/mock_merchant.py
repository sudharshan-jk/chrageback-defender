"""Mock merchant APIs. Return realistic evidence given an order_id.

These are the tools the agent calls to gather evidence during a dispute.
They read from data/mock_orders.json — treat that as the merchant's database.
"""
import json
from pathlib import Path
from typing import Any

_ORDERS_CACHE: dict[str, dict[str, Any]] | None = None


def _orders() -> dict[str, dict[str, Any]]:
    global _ORDERS_CACHE
    if _ORDERS_CACHE is None:
        raw = json.loads(Path("data/mock_orders.json").read_text(encoding="utf-8"))
        _ORDERS_CACHE = {o["order_id"]: o for o in raw}
    return _ORDERS_CACHE


def _get(order_id: str) -> dict[str, Any] | None:
    return _orders().get(order_id)


# --- Tool 1 ---
def get_order(order_id: str) -> dict[str, Any]:
    """Return basic order info: amount, customer, date, payment method."""
    o = _get(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    return {
        "order_id": o["order_id"],
        "customer_id": o["customer_id"],
        "customer_name": o["customer_name"],
        "amount_inr": o["amount_inr"],
        "currency": o["currency"],
        "payment_method": o["payment_method"],
        "created_at": o["created_at"],
    }


# --- Tool 2 ---
def get_delivery_proof(order_id: str) -> dict[str, Any]:
    """Return delivery evidence: carrier, tracking, delivery date. Empty if unavailable."""
    o = _get(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    has = o["_has_evidence"]
    result: dict[str, Any] = {}
    if has.get("proof_of_delivery") or has.get("tracking_number_with_carrier_name") or has.get("tracking_number_with_carrier"):
        result["carrier"] = o["carrier"]
        result["tracking_number"] = o["tracking_number"]
        result["delivered_at"] = o["delivered_at"]
    if has.get("signed_delivery_confirmation_if_over_threshold") or has.get("signed_pod_for_high_value"):
        result["signed_pod"] = True
    if not result:
        return {"available": False, "note": "no delivery evidence on file for this order"}
    result["available"] = True
    return result


# --- Tool 3 ---
def get_customer_communications(customer_id: str) -> dict[str, Any]:
    """Return customer email/support-ticket history for evidence of receipt or dispute cause."""
    # Look up the order via customer_id
    order = next((o for o in _orders().values() if o["customer_id"] == customer_id), None)
    if not order:
        return {"error": f"customer {customer_id} not found"}
    has = order["_has_evidence"]
    if has.get("customer_communication_showing_delivery") or has.get("customer_communication_showing_receipt") or has.get("customer_email_confirming_receipt"):
        return {
            "available": True,
            "messages": [
                {"date": order["delivered_at"], "channel": "email", "from": "customer",
                 "content": "Received the package, thanks!"},
            ],
        }
    return {"available": False, "messages": []}


# --- Tool 4 ---
def get_transaction_signals(order_id: str) -> dict[str, Any]:
    """Return fraud-relevant transaction signals: AVS, CVV2, 3DS, IP."""
    o = _get(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    return {
        "avs_result": o["avs_result"],
        "cvv2_result": o["cvv2_result"],
        "three_ds_result": o["three_ds_result"],
        "ip_country": o["ip_country"],
        "billing_shipping_match": o["billing_address_matches_shipping"],
    }


# --- Tool 5 ---
def get_ip_device_history(customer_id: str) -> dict[str, Any]:
    """Return device fingerprint + IP history for this customer."""
    order = next((o for o in _orders().values() if o["customer_id"] == customer_id), None)
    if not order:
        return {"error": f"customer {customer_id} not found"}
    has = order["_has_evidence"]
    if has.get("device_fingerprint_or_ip_history") or has.get("ip_and_device_fingerprint_data"):
        return {
            "available": True,
            "device_fingerprint": order["device_fingerprint"],
            "ip_country": order["ip_country"],
            "prior_logins": random.randint(2, 15) if False else 5,  # deterministic
        }
    return {"available": False}


# --- Tool 6 ---
def check_prior_chargebacks(customer_id: str) -> dict[str, Any]:
    """Return how many past chargebacks this customer has filed."""
    order = next((o for o in _orders().values() if o["customer_id"] == customer_id), None)
    if not order:
        return {"error": f"customer {customer_id} not found"}
    return {
        "customer_id": customer_id,
        "prior_chargebacks_count": order["prior_chargebacks_for_customer"],
    }


# Registry the agent will use
TOOL_REGISTRY = {
    "get_order": get_order,
    "get_delivery_proof": get_delivery_proof,
    "get_customer_communications": get_customer_communications,
    "get_transaction_signals": get_transaction_signals,
    "get_ip_device_history": get_ip_device_history,
    "check_prior_chargebacks": check_prior_chargebacks,
}


if __name__ == "__main__":
    orders_list = list(_orders().values())
    if not orders_list:
        print("no orders. run scripts/generate_data.py first.")
    else:
        oid = orders_list[0]["order_id"]
        cid = orders_list[0]["customer_id"]
        print(f"testing tools against {oid} / {cid}\n")

        # Tools that take an order_id
        for name in ["get_order", "get_delivery_proof", "get_transaction_signals"]:
            print(f"{name}({oid}):")
            print(json.dumps(TOOL_REGISTRY[name](oid), indent=2))
            print()

        # Tools that take a customer_id
        for name in ["get_customer_communications", "get_ip_device_history", "check_prior_chargebacks"]:
            print(f"{name}({cid}):")
            print(json.dumps(TOOL_REGISTRY[name](cid), indent=2))
            print()