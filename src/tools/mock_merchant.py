"""Mock merchant APIs. Each tool returns `evidence_provided`: the specific
evidence tokens it can vouch for on this order. This keeps agent output in
exact sync with the ground truth."""
import json
from pathlib import Path
from typing import Any

_ORDERS_CACHE: dict[str, dict[str, Any]] | None = None

# Which evidence tokens each tool is responsible for
TOOL_EVIDENCE = {
    "get_delivery_proof": [
        "proof_of_delivery", "tracking_number_with_carrier_name", "tracking_number_with_carrier",
        "signed_delivery_confirmation_if_over_threshold", "signed_pod_for_high_value",
        "proof_of_delivery_or_service_completion", "service_completion_documentation",
        "signed_delivery_confirmation_at_billing_address",
        "carrier_tracking_showing_delivery_before_dispute", "signed_pod_matching_shipping_address",
        "service_completion_signature_or_timestamp",
        "carrier_tracking_showing_delivery_to_billing_address",
        "signed_proof_of_delivery_for_high_value_orders",
        "delivery_signed_by_cardholder_at_billing_address",
    ],
    "get_customer_communications": [
        "customer_communication_showing_delivery", "customer_communication_showing_receipt",
        "customer_email_confirming_receipt", "customer_email_acknowledging_receipt",
        "customer_correspondence_prior_to_dispute",
        "download_or_access_logs_for_digital_goods", "digital_access_or_download_logs",
        "download_or_login_timestamp_after_purchase", "digital_product_download_timestamp",
    ],
    "get_transaction_signals": [
        "avs_match_result", "cvv2_match_result", "3ds_authentication_result",
        "avs_and_cvv2_match_results", "billing_and_shipping_address_match",
        "delivery_address_matches_billing_address",
        "3ds_liability_shift_authenticated_transaction",
        "avs_and_cvv2_full_match_on_billing_address",
        "3ds_liability_shift_verified_by_visa_or_securecode",
        "matching_avs_and_cvv2_at_billing_address",
        "billing_and_shipping_address_match_verified",
    ],
    "get_ip_device_history": [
        "device_fingerprint_or_ip_history", "ip_and_device_fingerprint_data",
        "customer_login_and_order_history",
        "ip_geolocation_matches_billing_or_delivery_address",
        "screenshot_of_customer_account_login_at_purchase_time",
    ],
    "check_prior_chargebacks": [
        "prior_transaction_history_with_customer",
        "prior_undisputed_orders_from_same_credentials",
        "prior_undisputed_orders_from_same_account",
    ],
}


def _orders() -> dict[str, dict[str, Any]]:
    global _ORDERS_CACHE
    if _ORDERS_CACHE is None:
        raw = json.loads(Path("data/mock_orders.json").read_text(encoding="utf-8"))
        _ORDERS_CACHE = {o["order_id"]: o for o in raw}
    return _ORDERS_CACHE


def _order_by_id(order_id: str):
    return _orders().get(order_id)


def _order_by_customer(customer_id: str):
    return next((o for o in _orders().values() if o["customer_id"] == customer_id), None)


def _provided(order: dict, tool_name: str) -> list[str]:
    """Which of this tool's evidence tokens does the order actually have?"""
    return [ev for ev in TOOL_EVIDENCE[tool_name] if order["_has_evidence"].get(ev, False)]


def get_order(order_id: str) -> dict[str, Any]:
    o = _order_by_id(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    return {
        "order_id": o["order_id"], "customer_id": o["customer_id"],
        "customer_name": o["customer_name"], "amount_inr": o["amount_inr"],
        "currency": o["currency"], "payment_method": o["payment_method"],
        "created_at": o["created_at"], "evidence_provided": [],
    }


def get_delivery_proof(order_id: str) -> dict[str, Any]:
    o = _order_by_id(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    provided = _provided(o, "get_delivery_proof")
    if not provided:
        return {"available": False, "evidence_provided": []}
    return {
        "available": True, "carrier": o["carrier"], "tracking_number": o["tracking_number"],
        "delivered_at": o["delivered_at"], "evidence_provided": provided,
    }


def get_customer_communications(customer_id: str) -> dict[str, Any]:
    o = _order_by_customer(customer_id)
    if not o:
        return {"error": f"customer {customer_id} not found"}
    provided = _provided(o, "get_customer_communications")
    if not provided:
        return {"available": False, "messages": [], "evidence_provided": []}
    return {
        "available": True,
        "messages": [{"date": o["delivered_at"], "channel": "email", "from": "customer",
                      "content": "Received the package, thanks!"}],
        "evidence_provided": provided,
    }


def get_transaction_signals(order_id: str) -> dict[str, Any]:
    o = _order_by_id(order_id)
    if not o:
        return {"error": f"order {order_id} not found"}
    provided = _provided(o, "get_transaction_signals")
    if not provided:
        return {"available": False, "evidence_provided": []}
    return {
        "available": True, "avs_result": o["avs_result"], "cvv2_result": o["cvv2_result"],
        "three_ds_result": o["three_ds_result"], "ip_country": o["ip_country"],
        "billing_shipping_match": o["billing_address_matches_shipping"],
        "evidence_provided": provided,
    }


def get_ip_device_history(customer_id: str) -> dict[str, Any]:
    o = _order_by_customer(customer_id)
    if not o:
        return {"error": f"customer {customer_id} not found"}
    provided = _provided(o, "get_ip_device_history")
    if not provided:
        return {"available": False, "evidence_provided": []}
    return {
        "available": True, "device_fingerprint": o["device_fingerprint"],
        "ip_country": o["ip_country"], "prior_logins": 5, "evidence_provided": provided,
    }


def check_prior_chargebacks(customer_id: str) -> dict[str, Any]:
    o = _order_by_customer(customer_id)
    if not o:
        return {"error": f"customer {customer_id} not found"}
    provided = _provided(o, "check_prior_chargebacks")
    if not provided:
        return {"available": False, "evidence_provided": []}
    return {
        "available": True, "customer_id": customer_id,
        "prior_chargebacks_count": o["prior_chargebacks_for_customer"],
        "evidence_provided": provided,
    }


TOOL_REGISTRY = {
    "get_order": get_order,
    "get_delivery_proof": get_delivery_proof,
    "get_customer_communications": get_customer_communications,
    "get_transaction_signals": get_transaction_signals,
    "get_ip_device_history": get_ip_device_history,
    "check_prior_chargebacks": check_prior_chargebacks,
}
