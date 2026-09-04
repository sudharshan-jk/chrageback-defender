"""Baseline: template-only representment responder.

No LLM. No triage. No evidence gathering. Given a reason code, emit the same
generic letter every time and always recommend fighting the dispute.

This is what a merchant with a Word template does today.
"""
import json
import time
from pathlib import Path
from pydantic import BaseModel

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))


class BaselineResult(BaseModel):
    dispute_id: str
    recommendation: str
    letter_text: str
    latency_ms: int


def _find_reason_code(network: str, code: str):
    for e in CORPUS:
        if e["network"].lower() == network.lower() and e["code"] == code:
            return e
    return None


def run_baseline(dispute: dict) -> BaselineResult:
    t0 = time.time()
    reason = _find_reason_code(dispute["network"], dispute["reason_code"])
    title = reason["title"] if reason else "the stated reason"

    letter = (
        "To the Issuing Bank Dispute Resolution Team,\n\n"
        f"We are writing in response to the chargeback filed under "
        f"{dispute['network']} reason code {dispute['reason_code']} ({title}).\n\n"
        "We dispute this chargeback. Our records indicate the transaction was "
        "valid and authorised by the cardholder. We have provided goods or "
        "services as agreed and have documentation supporting the transaction.\n\n"
        "We respectfully request that this chargeback be reversed and the funds "
        "returned to our account.\n\n"
        "Regards,\nMerchant Dispute Team"
    )

    return BaselineResult(
        dispute_id=dispute["dispute_id"],
        recommendation="fight",  # baseline always fights
        letter_text=letter,
        latency_ms=int((time.time() - t0) * 1000),
    )
