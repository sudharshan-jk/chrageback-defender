"""Classify a chargeback notice into a structured record.

Uses Groq gpt-oss-20b (fast, cheap) + retrieval context from Phase 2.
"""
import json
import re
from typing import Any
from pydantic import BaseModel, Field, ValidationError

from src.agent.llm import call_llm, MODEL_FAST
from src.retrieval import retrieve


class Classification(BaseModel):
    reason_code: str = Field(..., description="e.g. '4855' or '10.4'")
    network: str = Field(..., description="visa | mastercard | rupay | amex")
    amount: float | None = None
    currency: str | None = None
    transaction_id: str | None = None
    dispute_id: str | None = None
    order_id: str | None = None
    customer_name: str | None = None
    deadline_days: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str

    @classmethod
    def _post_validate(cls, obj: "Classification") -> "Classification":
        obj.network = obj.network.lower().strip()
        parts = obj.reason_code.strip().split()
        if len(parts) > 1 and parts[0].lower() in {"visa", "mastercard", "rupay", "amex"}:
            obj.reason_code = " ".join(parts[1:])
        return obj


SYSTEM = """You classify chargeback notices into structured JSON.

Return ONLY a JSON object with these exact fields:
- reason_code: the code ALONE, e.g. "4855" or "10.4" (never include network name in this field)
- network: lowercase, one of "visa", "mastercard", "rupay", "amex"
- amount: number if in notice, else null
- currency: string if in notice, else null
- transaction_id, dispute_id, order_id, customer_name: strings if in notice, else null
- deadline_days: integer if stated, else null
- confidence: 0.0 to 1.0
- reasoning: one short sentence

Rules:
- If the notice STATES a reason code and network directly (e.g. "Network: MASTERCARD, Reason Code: 4855"), use those exactly.
- Otherwise pick from the candidates below.
- reason_code must be the code only, no network prefix.
- network must be lowercase.

Return only the JSON object. No prose, no markdown fences."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def classify(notice_text: str) -> Classification:
    """Classify a chargeback notice into a Classification object."""
    # Retrieve top-5 candidate reason codes
    candidates = retrieve(notice_text, k=5)
    candidate_lines = "\n".join(
        f"- {c['network']} {c['code']}: {c['title']} — {c['short_description']}"
        for c in candidates
    )

    user_msg = (
        f"NOTICE:\n{notice_text}\n\n"
        f"CANDIDATE REASON CODES (top 5 by retrieval):\n{candidate_lines}\n\n"
        f"Return the JSON object now."
    )

    raw = call_llm(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        model=MODEL_FAST,
        max_tokens=1500,
        json_mode=True,
    )

    try:
        return Classification.model_validate_json(_strip_fences(raw))
    except ValidationError as e:
        # One retry with the error appended
        retry_msg = f"{user_msg}\n\nYour previous response failed validation: {e}. Return valid JSON."
        raw = call_llm(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": retry_msg},
            ],
            model=MODEL_FAST,
            max_tokens=1500,
            json_mode=True,
        )
        return Classification.model_validate_json(_strip_fences(raw))


if __name__ == "__main__":
    # Smoke test with a fake notice
    sample = (
        "CHARGEBACK NOTICE\n"
        "Dispute ID: disp_2001\n"
        "Transaction ID: txn_1005\n"
        "Order ID: ord_1005\n"
        "Amount: INR 4200.00\n"
        "Cardholder: Priya Sharma\n"
        "Network: MASTERCARD\n"
        "Reason Code: 4855\n"
        "Reason: Goods or Services Not Provided\n"
        "Description: Cardholder claims package never arrived."
    )
    result = classify(sample)
    print(result.model_dump_json(indent=2))