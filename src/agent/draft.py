"""Draft a representment letter grounded in gathered evidence and network rules.

Uses the smart model (gpt-oss-120b). Every factual claim must carry a citation
pointing at either a tool call or a rule from the reason-code corpus.
"""
import json
import re
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError

from src.agent.llm import call_llm, MODEL_SMART
from src.agent.gather import GatherResult

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))


class Claim(BaseModel):
    text: str = Field(..., description="One factual sentence for the letter")
    citation: str = Field(..., description="tool:NAME or rule:NETWORK-CODE")


class Representment(BaseModel):
    salutation: str
    claims: list[Claim]
    closing: str


SYSTEM = """You draft chargeback representment letters for merchants.

You will receive:
- the dispute details (reason code, network, amounts, IDs)
- the network's stated evidence requirements for this reason code
- the evidence the merchant actually has, from tool calls

Write a representment letter as a list of factual claims. Rules:

1. EVERY claim must have a citation. Format: "tool:get_delivery_proof" for
   evidence from a tool call, or "rule:mastercard-4855" for a network rule.
2. NEVER state a fact you cannot cite. If evidence is missing, either omit the
   claim or acknowledge the gap honestly with a rule citation.
3. Your FIRST claim must be an opening that states the dispute ID, transaction
   ID, order ID, amount, and cardholder name verbatim as given. These exact
   strings must appear in the letter text — the letter is rejected without them.
4. Then include claims covering each piece of evidence gathered, and why that
   evidence rebuts the specific reason code.
4. Keep each claim to one clear sentence. Professional, factual tone.
5. Do not invent order IDs, tracking numbers, dates, or amounts. Use only what
   appears in the evidence provided.

Return ONLY a JSON object:
{"salutation": "...", "claims": [{"text": "...", "citation": "..."}], "closing": "..."}

No prose, no markdown fences."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _find_reason_code(network: str, code: str):
    for e in CORPUS:
        if e["network"].lower() == network.lower() and e["code"] == code:
            return e
    return None


def draft(result: GatherResult) -> Representment:
    """Draft a representment letter from a GatherResult."""
    cls = result.classification
    reason = _find_reason_code(cls.network, cls.reason_code)

    rule_text = ""
    if reason:
        rule_text = (
            f"Reason code {reason['network']} {reason['code']}: {reason['title']}\n"
            f"{reason['short_description']}\n"
            f"Required evidence: {', '.join(reason['required_evidence'])}\n"
            f"Typical winning defenses: {', '.join(reason['typical_defenses'])}\n"
            f"Merchant response deadline: {reason['deadline_days']} days\n"
            f"Source: {reason['source_citation']}"
        )

    evidence_text = "\n".join(
        f"- {c.tool} returned: {json.dumps(c.output)}"
        for c in result.tools_called
    )

    user_msg = (
        f"DISPUTE:\n"
        f"  dispute_id: {cls.dispute_id}\n"
        f"  transaction_id: {cls.transaction_id}\n"
        f"  order_id: {result.order_id}\n"
        f"  amount: {cls.amount} {cls.currency}\n"
        f"  cardholder: {cls.customer_name}\n"
        f"  network: {cls.network}\n"
        f"  reason_code: {cls.reason_code}\n\n"
        f"NETWORK RULE:\n{rule_text}\n\n"
        f"EVIDENCE GATHERED:\n{evidence_text}\n\n"
        f"EVIDENCE PRESENT: {', '.join(result.evidence_present) or 'none'}\n"
        f"EVIDENCE MISSING: {', '.join(result.evidence_missing) or 'none'}\n"
        f"WINNABILITY: {result.winnability}\n\n"
        f"Draft the representment letter now. Return the JSON object."
    )

    raw = call_llm(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        model=MODEL_SMART,
        max_tokens=3000,
        json_mode=True,
    )

    try:
        return Representment.model_validate_json(_strip_fences(raw))
    except ValidationError as e:
        retry = f"{user_msg}\n\nPrevious response failed validation: {e}. Return valid JSON."
        raw = call_llm(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": retry},
            ],
            model=MODEL_SMART,
            max_tokens=3000,
            json_mode=True,
        )
        return Representment.model_validate_json(_strip_fences(raw))


def render_letter(rep: Representment) -> str:
    """Render a Representment as plain text (citations stripped)."""
    lines = [rep.salutation, ""]
    for c in rep.claims:
        lines.append(c.text)
    lines.extend(["", rep.closing])
    return "\n".join(lines)


def render_letter_with_citations(rep: Representment) -> str:
    """Render with inline citations, for the demo UI."""
    lines = [rep.salutation, ""]
    for c in rep.claims:
        lines.append(f"{c.text}  [{c.citation}]")
    lines.extend(["", rep.closing])
    return "\n".join(lines)

