"""Given a classification, call the merchant tools and compute winnability."""
import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from src.agent.classify import Classification
from src.tools.mock_merchant import TOOL_REGISTRY

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))

# Only map evidence types to tools that ACTUALLY return that evidence.
# Being loose here inflates winnability scores and defeats the eval.
EVIDENCE_TO_TOOL = {
    # get_delivery_proof returns carrier, tracking, delivered_at, signed_pod
    "proof_of_delivery": "get_delivery_proof",
    "tracking_number_with_carrier_name": "get_delivery_proof",
    "tracking_number_with_carrier": "get_delivery_proof",
    "signed_delivery_confirmation_if_over_threshold": "get_delivery_proof",
    "signed_pod_for_high_value": "get_delivery_proof",
    "proof_of_delivery_or_service_completion": "get_delivery_proof",
    "service_completion_documentation": "get_delivery_proof",
    "signed_delivery_confirmation_at_billing_address": "get_delivery_proof",
    "carrier_tracking_showing_delivery_before_dispute": "get_delivery_proof",
    "signed_pod_matching_shipping_address": "get_delivery_proof",
    "service_completion_signature_or_timestamp": "get_delivery_proof",
    "carrier_tracking_showing_delivery_to_billing_address": "get_delivery_proof",
    "signed_proof_of_delivery_for_high_value_orders": "get_delivery_proof",
    # get_customer_communications returns customer email messages (currently only receipt confirmations)
    "customer_communication_showing_delivery": "get_customer_communications",
    "customer_communication_showing_receipt": "get_customer_communications",
    "customer_email_confirming_receipt": "get_customer_communications",
    "customer_email_acknowledging_receipt": "get_customer_communications",
    "customer_correspondence_prior_to_dispute": "get_customer_communications",
    # get_transaction_signals returns AVS/CVV2/3DS/IP data
    "avs_match_result": "get_transaction_signals",
    "cvv2_match_result": "get_transaction_signals",
    "3ds_authentication_result": "get_transaction_signals",
    "avs_and_cvv2_match_results": "get_transaction_signals",
    "billing_and_shipping_address_match": "get_transaction_signals",
    "delivery_address_matches_billing_address": "get_transaction_signals",
    "3ds_liability_shift_authenticated_transaction": "get_transaction_signals",
    "avs_and_cvv2_full_match_on_billing_address": "get_transaction_signals",
    "3ds_liability_shift_verified_by_visa_or_securecode": "get_transaction_signals",
    "matching_avs_and_cvv2_at_billing_address": "get_transaction_signals",
    # get_ip_device_history returns device fingerprint + IP country
    "device_fingerprint_or_ip_history": "get_ip_device_history",
    "ip_and_device_fingerprint_data": "get_ip_device_history",
    "customer_login_and_order_history": "get_ip_device_history",
    "ip_geolocation_matches_billing_or_delivery_address": "get_ip_device_history",
    "screenshot_of_customer_account_login_at_purchase_time": "get_ip_device_history",
    # check_prior_chargebacks returns count of past chargebacks
    "prior_transaction_history_with_customer": "check_prior_chargebacks",
    "prior_undisputed_orders_from_same_credentials": "check_prior_chargebacks",
    "prior_undisputed_orders_from_same_account": "check_prior_chargebacks",
    "digital_product_download_timestamp": "get_customer_communications",
    "digital_access_or_download_logs": "get_customer_communications",
    "download_or_access_logs_for_digital_goods": "get_customer_communications",
    "download_or_login_timestamp_after_purchase": "get_customer_communications",
    "delivery_signed_by_cardholder_at_billing_address": "get_delivery_proof",
    "billing_and_shipping_address_match_verified": "get_transaction_signals",
    # NOT MAPPED — no tool provides these (deliberately unmapped = "missing"):
    #   proof_credit_issued, cancellation_policy, merchant_communication,
    #   refund_processing_records_*, cancellation_policy_and_customer_acknowledgement_*,
    #   signed_cancellation_terms_shown_at_checkout, product_description_and_condition_*,
    #   product_listing_screenshot_and_return_policy, sub_dispute_reason_from_issuer,
    #   authorization_approval_code, transaction_receipt, terminal_audit_log,
    #   itemized_receipt, proof_of_separate_transactions, currency_conversion_log,
    #   download_or_access_logs_for_digital_goods, digital_access_or_download_logs,
    #   download_or_login_timestamp_after_purchase, digital_product_download_timestamp,
    #   billing_descriptor_clarity, agreed_delivery_date_documentation, etc.
    # These represent evidence types a real merchant tool would need to expose.
    # Treating them as "missing" is honest: mock tools don't return them.
}

CUSTOMER_TOOLS = {"get_customer_communications", "get_ip_device_history", "check_prior_chargebacks"}


class Evidence(BaseModel):
    tool: str
    input_arg: str
    output: dict[str, Any]
    covers_evidence_types: list[str]


class GatherResult(BaseModel):
    classification: Classification
    order_id: str | None
    required_evidence: list[str]
    tools_called: list[Evidence]
    evidence_present: list[str]
    evidence_missing: list[str]
    winnability: float = Field(..., ge=0.0, le=1.0)
    recommendation: str


def _find_reason_code(network: str, code: str):
    for e in CORPUS:
        if e["network"].lower() == network.lower() and e["code"] == code:
            return e
    return None


def _evidence_provided(tool_name: str, tool_output: dict) -> bool:
    if not tool_output or "error" in tool_output:
        return False
    if tool_output.get("available") is False:
        return False
    if tool_name == "get_customer_communications" and not tool_output.get("messages"):
        return False
    return True


def gather(cls: Classification, order_id: str | None = None, customer_id: str | None = None) -> GatherResult:
    order_id = order_id or cls.order_id
    if not order_id:
        raise ValueError("no order_id available")

    reason_entry = _find_reason_code(cls.network, cls.reason_code)
    required = reason_entry["required_evidence"] if reason_entry else []

    if not customer_id:
        order_data = TOOL_REGISTRY["get_order"](order_id)
        customer_id = order_data.get("customer_id")

    tools_needed: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for ev in required:
        tool = EVIDENCE_TO_TOOL.get(ev)
        if tool:
            tools_needed.setdefault(tool, []).append(ev)
        else:
            unmapped.append(ev)

    tools_needed.setdefault("get_order", [])
    tools_needed.setdefault("get_transaction_signals", [])

    calls: list[Evidence] = []
    for tool_name, covers in tools_needed.items():
        fn = TOOL_REGISTRY[tool_name]
        if tool_name in CUSTOMER_TOOLS:
            arg = customer_id
        else:
            arg = order_id
        output = fn(arg)
        calls.append(Evidence(
            tool=tool_name,
            input_arg=str(arg),
            output=output,
            covers_evidence_types=covers,
        ))

    # Collect every evidence token that any tool explicitly vouched for
    vouched: set[str] = set()
    for c in calls:
        vouched.update(c.output.get("evidence_provided", []))

    present: list[str] = []
    missing: list[str] = list(unmapped)
    for ev in required:
        if ev in unmapped:
            continue
        if ev in vouched:
            present.append(ev)
        else:
            missing.append(ev)

    gatherable_required = [ev for ev in required if ev not in unmapped]
    winnability = len(present) / len(gatherable_required) if gatherable_required else 0.0
    if winnability >= 0.99:
        rec = "fight"
    elif winnability >= 0.6:
        rec = "review"
    else:
        rec = "accept"

    return GatherResult(
        classification=cls,
        order_id=order_id,
        required_evidence=required,
        tools_called=calls,
        evidence_present=present,
        evidence_missing=missing,
        winnability=round(winnability, 2),
        recommendation=rec,
    )


if __name__ == "__main__":
    import sys
    disputes = json.loads(Path("data/disputes.json").read_text(encoding="utf-8"))
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    d = disputes[idx]
    print(f"testing dispute #{idx}: {d['dispute_id']} (ground_truth_winnable={d['ground_truth_winnable']})\n")

    from src.agent.classify import classify
    cls = classify(d["notice_text"])
    print("classification:")
    print(cls.model_dump_json(indent=2))
    print()

    result = gather(cls, order_id=d["order_id"])
    print("gather result:")
    print(result.model_dump_json(indent=2))
    print()
    print(f"AGREEMENT WITH GROUND TRUTH: {(result.recommendation == 'fight') == d['ground_truth_winnable']}")




