"""LLM-as-judge: score representment letter quality with Gemini 3.6 Flash.

Deliberately a different model family from the drafter (Groq gpt-oss) so the
judge is not grading its own work.
"""
import json
import os
import re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

RUBRIC = """Score this chargeback representment letter from 0 to 10 on each dimension:

1. SPECIFICITY (0-10): Does it cite concrete evidence (tracking numbers, AVS/CVV
   results, dates, IDs) rather than generic assertions?
2. RULE_ALIGNMENT (0-10): Does it address the specific evidence requirements of
   the stated reason code, rather than making a generic defense?
3. HONESTY (0-10): Does it acknowledge gaps in evidence rather than overclaiming?
   Overclaiming (asserting evidence that wasn't provided) scores 0-2.
4. PERSUASIVENESS (0-10): Would an issuing-bank reviewer find this convincing?

Return ONLY JSON: {"specificity": N, "rule_alignment": N, "honesty": N, "persuasiveness": N, "note": "one sentence"}"""


def judge_letter(letter_text: str, reason_code: str, network: str, evidence_summary: str) -> dict:
    prompt = (
        f"{RUBRIC}\n\n"
        f"REASON CODE: {network} {reason_code}\n"
        f"EVIDENCE ACTUALLY AVAILABLE TO THE MERCHANT:\n{evidence_summary}\n\n"
        f"LETTER:\n{letter_text}\n\n"
        f"Return the JSON scores now."
    )
    for attempt in range(3):
        try:
            r = _client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=2000,
                ),
            )
            text = r.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            scores = json.loads(text)
            scores["total"] = (
                scores.get("specificity", 0) + scores.get("rule_alignment", 0)
                + scores.get("honesty", 0) + scores.get("persuasiveness", 0)
            ) / 4.0
            return scores
        except Exception as e:
            if attempt == 2:
                return {"specificity": 0, "rule_alignment": 0, "honesty": 0,
                        "persuasiveness": 0, "total": 0.0, "note": f"judge_error: {e}"}
            time.sleep(3 * (attempt + 1))
    return {"total": 0.0, "note": "judge_exhausted"}
