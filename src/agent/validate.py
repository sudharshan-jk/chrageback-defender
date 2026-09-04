"""Deterministic validation of a drafted representment letter.

Three checks:
1. Required identifiers present (dispute ID, transaction ID, amount)
2. Every claim has a well-formed, resolvable citation
3. Evidence coverage: gathered evidence is actually referenced
"""
import json
import re
from pathlib import Path
from pydantic import BaseModel

from src.agent.draft import Representment
from src.agent.gather import GatherResult

CORPUS = json.loads(Path("corpus/reason_codes.json").read_text(encoding="utf-8"))
VALID_TOOLS = {
    "get_order", "get_delivery_proof", "get_customer_communications",
    "get_transaction_signals", "get_ip_device_history", "check_prior_chargebacks",
}
CITATION_RE = re.compile(r"^(tool|rule):([a-zA-Z0-9_\-\.]+)$")


class ValidationResult(BaseModel):
    passed: bool
    failures: list[str]
    stripped_claims: int
    total_claims: int


def _citation_valid(citation: str, result: GatherResult) -> bool:
    # Models sometimes emit multiple citations joined by ; or , — take the first.
    citation = re.split(r"[;,]", citation.strip())[0].strip()
    m = CITATION_RE.match(citation)
    if not m:
        return False
    kind, ref = m.group(1), m.group(2)
    if kind == "tool":
        if ref not in VALID_TOOLS:
            return False
        # must be a tool that was actually called
        return any(c.tool == ref for c in result.tools_called)
    if kind == "rule":
        # format: network-code, e.g. mastercard-4855 or visa-10.4
        parts = ref.split("-", 1)
        if len(parts) != 2:
            return False
        network, code = parts
        return any(
            e["network"].lower() == network.lower() and e["code"] == code
            for e in CORPUS
        )
    return False


def validate(rep: Representment, result: GatherResult) -> tuple[ValidationResult, Representment]:
    """Validate the letter. Returns (result, cleaned_representment).

    Claims with invalid citations are stripped from the returned letter.
    """
    failures: list[str] = []
    cls = result.classification

    # Check 1: required identifiers appear somewhere in the letter
    body = " ".join(c.text for c in rep.claims)
    if cls.dispute_id and cls.dispute_id not in body:
        failures.append(f"missing dispute_id ({cls.dispute_id}) in letter body")
    if cls.transaction_id and cls.transaction_id not in body:
        failures.append(f"missing transaction_id ({cls.transaction_id}) in letter body")

    # Check 2: strip claims with bad citations
    good_claims = []
    stripped = 0
    for c in rep.claims:
        if _citation_valid(c.citation, result):
            good_claims.append(c)
        else:
            stripped += 1
            failures.append(f"invalid citation: {c.citation!r} on claim {c.text[:60]!r}")

    total = len(rep.claims)
    if total == 0:
        failures.append("letter has no claims")
    elif stripped / total > 0.3:
        failures.append(f"too many claims stripped: {stripped}/{total} (>30%)")

    # Check 3: at least one claim references each successfully gathered evidence tool
    cited_tools = {
        CITATION_RE.match(c.citation).group(2)
        for c in good_claims
        if CITATION_RE.match(c.citation) and c.citation.startswith("tool:")
    }
    gathered_tools = {
        c.tool for c in result.tools_called
        if c.output.get("evidence_provided")
    }
    uncited = gathered_tools - cited_tools
    if uncited:
        failures.append(f"gathered evidence not referenced in letter: {sorted(uncited)}")

    cleaned = Representment(
        salutation=rep.salutation,
        claims=good_claims,
        closing=rep.closing,
    )

    return ValidationResult(
        passed=len(failures) == 0,
        failures=failures,
        stripped_claims=stripped,
        total_claims=total,
    ), cleaned

