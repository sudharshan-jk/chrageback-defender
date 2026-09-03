"""Extract reason codes from a PDF into structured JSON via Gemini.

Reads the PDF locally with pypdf, sends the extracted text to Gemini.
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader

load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

PROMPT = """You are extracting chargeback reason codes from the text below.

Return a JSON array. Each element must have these exact fields:
- code (string): the numeric or alphanumeric identifier, e.g. "4855" or "10.4"
- network (string): "{network}"
- category (string): one of "fraud", "consumer_dispute", "processing_error", "authorization", "cancelled_recurring"
- title (string): short human-readable name
- short_description (string): 1-2 sentences on what the code means
- required_evidence (array of strings): 3-5 snake_case tokens like "proof_of_delivery"
- typical_defenses (array of strings): 3-5 snake_case tokens for winning evidence
- deadline_days (integer): merchant response deadline in days (use 30 if unclear)
- source_citation (string): reference to where in the source this came from

Extract every distinct reason code you see. Do not invent codes.
Output ONLY the JSON array. No prose, no markdown, no code fences.

--- DOCUMENT TEXT ---
{doc_text}
"""


def read_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n\n".join(parts)


def extract_from(pdf_path: str, network: str) -> list[dict]:
    doc_text = read_pdf_text(pdf_path)
    print(f"  extracted {len(doc_text)} chars from PDF")
    prompt = PROMPT.format(network=network, doc_text=doc_text)

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=16000,
        ),
    )
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/extract_codes.py <pdf_path> <network>")
        sys.exit(1)

    pdf_path, network = sys.argv[1], sys.argv[2]
    print(f"extracting from {pdf_path} (network={network})...")

    entries = extract_from(pdf_path, network)

    out = Path("corpus/reason_codes.json")
    existing = json.loads(out.read_text(encoding="utf-8"))
    existing.extend(entries)
    out.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print(f"added {len(entries)} entries. total now: {len(existing)}")