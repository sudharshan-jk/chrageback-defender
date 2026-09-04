"""Template representment letters, used when the LLM path fails.

Deterministic. No LLM call. Slots filled from the GatherResult.
"""
import json
from pathlib import Path

from src.agent.draft import Representment, Claim
from src.agent.gather import GatherResult

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))


def _find_reason_code(network: str, code: str):
    for e in CORPUS:
        if e["network"].lower() == network.lower() and e["code"] == code:
            return e
    return None


def template_letter(result: GatherResult, reason_tag: str = "fallback") -> Representment:
    """Build a generic but valid representment letter from gathered evidence."""
    cls = result.classification
    reason = _find_reason_code(cls.network, cls.reason_code)
    rule_cite = f"rule:{cls.network}-{cls.reason_code}"

    claims: list[Claim] = [
        Claim(
            text=(
                f"We are responding to dispute {cls.dispute_id} concerning "
                f"transaction {cls.transaction_id} for {cls.currency or 'INR'} "
                f"{cls.amount} placed by {cls.customer_name or 'the cardholder'}."
            ),
            citation="tool:get_order",
        ),
        Claim(
            text=(
                f"This dispute was filed under {cls.network} reason code "
                f"{cls.reason_code}"
                + (f" ({reason['title']})." if reason else ".")
            ),
            citation=rule_cite,
        ),
    ]

    # One claim per tool that returned real evidence
    for call in result.tools_called:
        provided = call.output.get("evidence_provided") or []
        if not provided:
            continue
        if call.tool == "get_delivery_proof":
            claims.append(Claim(
                text=(
                    f"Delivery records show the order was shipped via "
                    f"{call.output.get('carrier')} under tracking number "
                    f"{call.output.get('tracking_number')} and delivered on "
                    f"{str(call.output.get('delivered_at'))[:10]}."
                ),
                citation="tool:get_delivery_proof",
            ))
        elif call.tool == "get_transaction_signals":
            claims.append(Claim(
                text=(
                    f"Transaction authentication signals were captured: AVS "
                    f"{call.output.get('avs_result')}, CVV2 "
                    f"{call.output.get('cvv2_result')}, 3DS "
                    f"{call.output.get('three_ds_result')}."
                ),
                citation="tool:get_transaction_signals",
            ))
        elif call.tool == "get_customer_communications":
            claims.append(Claim(
                text="Customer correspondence on file confirms receipt of the order.",
                citation="tool:get_customer_communications",
            ))
        elif call.tool == "get_ip_device_history":
            claims.append(Claim(
                text=(
                    f"Device and network records place the order at IP country "
                    f"{call.output.get('ip_country')} with a known device fingerprint."
                ),
                citation="tool:get_ip_device_history",
            ))
        elif call.tool == "check_prior_chargebacks":
            claims.append(Claim(
                text=(
                    f"This cardholder has "
                    f"{call.output.get('prior_chargebacks_count')} prior chargebacks "
                    f"on record with this merchant."
                ),
                citation="tool:check_prior_chargebacks",
            ))

    if result.evidence_missing:
        claims.append(Claim(
            text=(
                f"We note that the following evidence types required by this "
                f"reason code are not available in our records: "
                f"{', '.join(result.evidence_missing)}."
            ),
            citation=rule_cite,
        ))

    return Representment(
        salutation="To the Issuing Bank Dispute Resolution Team,",
        claims=claims,
        closing=(
            "On the basis of the evidence above, we respectfully request that "
            "this chargeback be reversed. Supporting documentation is attached.\n\n"
            "Regards,\nMerchant Dispute Team"
        ),
    )
