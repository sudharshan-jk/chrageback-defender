"""ChargebackDefender demo UI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import streamlit as st

from src.agent.run import run_case

st.set_page_config(page_title="ChargebackDefender", page_icon="🛡️", layout="wide")

DISPUTES = json.loads(Path("data/disputes.json").read_text(encoding="utf-8"))


def _pick_demo_cases():
    """Curate three demo cases: a clear win, a review case, and an accept case."""
    picks = {}
    for i, d in enumerate(DISPUTES):
        if d["ground_truth_winnable"] and "win" not in picks:
            picks["win"] = (i, d)
        if not d["ground_truth_winnable"] and "lose" not in picks:
            picks["lose"] = (i, d)
        if len(picks) == 2:
            break
    return picks


st.title("🛡️ ChargebackDefender")
st.caption(
    "An AI agent that reads a chargeback notice, gathers evidence from merchant "
    "systems, and drafts a network-compliant representment letter — or tells you "
    "to accept the chargeback when the evidence isn't there."
)

# --- Input ---
col_a, col_b = st.columns([3, 1])

with col_b:
    st.markdown("**Load a sample**")
    demo = _pick_demo_cases()
    sample_choice = st.radio(
        "Sample dispute",
        options=["(none)"] + [f"#{i} — {d['reason_code']} ({'winnable' if d['ground_truth_winnable'] else 'weak evidence'})"
                              for i, d in demo.values()],
        label_visibility="collapsed",
    )

prefill = ""
prefill_order = ""
if sample_choice != "(none)":
    idx = int(sample_choice.split("—")[0].strip().lstrip("#"))
    prefill = DISPUTES[idx]["notice_text"]
    prefill_order = DISPUTES[idx]["order_id"]

with col_a:
    notice = st.text_area("Chargeback notice", value=prefill, height=240,
                          placeholder="Paste the chargeback notice here...")
    order_id = st.text_input("Order ID (optional — extracted from notice if omitted)",
                             value=prefill_order)

run = st.button("Analyse dispute", type="primary", use_container_width=True)

if run and notice.strip():
    with st.spinner("Classifying, gathering evidence, drafting..."):
        result = run_case(notice, order_id=order_id.strip() or None)

    # --- Top-line verdict ---
    rec = result.recommendation
    colour = {"fight": "🟢", "review": "🟡", "accept": "🔴"}[rec]
    verdict = {
        "fight": "FIGHT — evidence is complete, letter ready to send",
        "review": "REVIEW — partial evidence, merchant should check before filing",
        "accept": "ACCEPT — insufficient evidence, fighting this wastes the response window",
    }[rec]

    st.markdown("---")
    st.subheader(f"{colour} {verdict}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Winnability", f"{result.gather.winnability:.0%}")
    m2.metric("Reason code", f"{result.classification.network} {result.classification.reason_code}")
    m3.metric("Latency", f"{result.latency_ms / 1000:.1f}s")
    m4.metric("Fallback", "yes" if result.used_fallback else "no")

    if result.used_fallback:
        st.warning(f"⚠️ Validation rejected the LLM draft — fell back to a template letter.\n\n"
                   f"Reason: `{result.fallback_reason}`")

    # --- Evidence ---
    st.markdown("---")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**✅ Evidence present**")
        if result.gather.evidence_present:
            for ev in result.gather.evidence_present:
                st.markdown(f"- `{ev}`")
        else:
            st.markdown("_none_")
    with e2:
        st.markdown("**❌ Evidence missing**")
        if result.gather.evidence_missing:
            for ev in result.gather.evidence_missing:
                st.markdown(f"- `{ev}`")
        else:
            st.markdown("_none_")

    # --- Tool calls ---
    with st.expander(f"🔧 Tool calls ({len(result.gather.tools_called)})"):
        for call in result.gather.tools_called:
            provided = call.output.get("evidence_provided") or []
            badge = f"✅ {len(provided)} evidence types" if provided else "— no evidence"
            st.markdown(f"**`{call.tool}({call.input_arg})`** — {badge}")
            st.json(call.output, expanded=False)

    # --- Validation ---
    if result.validation:
        with st.expander(f"🔎 Validation — {'passed' if result.validation.passed else 'failed'}"):
            st.write(f"Claims: {result.validation.total_claims}, "
                     f"stripped: {result.validation.stripped_claims}")
            for f in result.validation.failures:
                st.markdown(f"- {f}")

    # --- Letter ---
    st.markdown("---")
    if result.letter_text:
        st.subheader("📄 Representment letter")
        st.text(result.letter_text)
        st.download_button("Download letter", result.letter_text,
                           file_name=f"representment_{result.dispute_id}.txt")
    else:
        st.subheader("No letter drafted")
        st.info(
            "The agent recommends accepting this chargeback. Required evidence is "
            "missing, and filing a representment without it typically loses — "
            "burning the merchant's one response opportunity."
        )

elif run:
    st.error("Paste a chargeback notice first.")
