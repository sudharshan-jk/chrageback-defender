"""End-to-end pipeline: notice text -> recommendation + letter (or accept advice).

Routing:
  winnability < 0.6   -> recommend accept, no letter drafted
  0.6 <= w < 0.99     -> draft + validate, flag for merchant review
  w >= 0.99           -> draft + validate, ready to send

On any LLM or validation failure -> template fallback, tagged with the reason.
"""
import json
import time
from pathlib import Path
from typing import Any
from pydantic import BaseModel

from src.agent.classify import classify, Classification
from src.agent.gather import gather, GatherResult
from src.agent.draft import draft, Representment, render_letter_with_citations
from src.agent.validate import validate, ValidationResult
from src.agent.fallback import template_letter


class CaseResult(BaseModel):
    dispute_id: str | None
    classification: Classification
    gather: GatherResult
    recommendation: str
    letter: Representment | None
    letter_text: str | None
    validation: ValidationResult | None
    used_fallback: bool
    fallback_reason: str | None
    needs_merchant_review: bool
    latency_ms: int


def run_case(notice_text: str, order_id: str | None = None) -> CaseResult:
    t0 = time.time()

    cls = classify(notice_text)
    result = gather(cls, order_id=order_id)

    used_fallback = False
    fallback_reason: str | None = None
    letter: Representment | None = None
    validation: ValidationResult | None = None

    if result.recommendation == "accept":
        # Don't waste a smart-model call on an unwinnable dispute
        return CaseResult(
            dispute_id=cls.dispute_id,
            classification=cls,
            gather=result,
            recommendation="accept",
            letter=None,
            letter_text=None,
            validation=None,
            used_fallback=False,
            fallback_reason=None,
            needs_merchant_review=False,
            latency_ms=int((time.time() - t0) * 1000),
        )

    # Try the LLM draft
    try:
        raw_letter = draft(result)
        validation, cleaned = validate(raw_letter, result)
        if validation.passed:
            letter = cleaned
        else:
            used_fallback = True
            fallback_reason = f"validation_failed: {validation.failures[0]}"
            letter = template_letter(result, reason_tag=fallback_reason)
    except Exception as e:
        used_fallback = True
        fallback_reason = f"llm_error: {type(e).__name__}: {e}"
        letter = template_letter(result, reason_tag=fallback_reason)

    return CaseResult(
        dispute_id=cls.dispute_id,
        classification=cls,
        gather=result,
        recommendation=result.recommendation,
        letter=letter,
        letter_text=render_letter_with_citations(letter) if letter else None,
        validation=validation,
        used_fallback=used_fallback,
        fallback_reason=fallback_reason,
        needs_merchant_review=(result.recommendation == "review"),
        latency_ms=int((time.time() - t0) * 1000),
    )


if __name__ == "__main__":
    import sys
    disputes = json.loads(Path("data/disputes.json").read_text(encoding="utf-8"))
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    d = disputes[idx]

    print(f"=== dispute #{idx}: {d['dispute_id']} ({d['reason_code']}) ===")
    print(f"ground truth winnable: {d['ground_truth_winnable']}\n")

    r = run_case(d["notice_text"], order_id=d["order_id"])

    print(f"recommendation:   {r.recommendation}")
    print(f"winnability:      {r.gather.winnability}")
    print(f"used fallback:    {r.used_fallback}" + (f" ({r.fallback_reason})" if r.fallback_reason else ""))
    print(f"needs review:     {r.needs_merchant_review}")
    print(f"latency:          {r.latency_ms}ms")
    if r.validation:
        print(f"validation:       passed={r.validation.passed}, stripped={r.validation.stripped_claims}/{r.validation.total_claims}")
        for f in r.validation.failures[:3]:
            print(f"    - {f}")
    print()
    if r.letter_text:
        print("--- LETTER ---")
        print(r.letter_text)
    else:
        print("(no letter drafted - recommendation is to accept the chargeback)")
