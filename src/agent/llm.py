"""Shared LLM client for Groq (OpenAI-compatible) with retry on rate limits."""
import os
import time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

load_dotenv()

_client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

MODEL_FAST = "openai/gpt-oss-20b"    # classification, extraction
MODEL_SMART = "openai/gpt-oss-120b"  # letter drafting (used in phase 5)


def call_llm(
    messages: list[dict],
    model: str = MODEL_FAST,
    max_tokens: int = 2000,
    json_mode: bool = False,
    max_retries: int = 3,
) -> str:
    """Call Groq with exponential backoff on rate limits."""
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries):
        try:
            r = _client.chat.completions.create(**kwargs)
            return r.choices[0].message.content or ""
        except RateLimitError:
            wait = 5 * (3 ** attempt)  # 5s, 15s, 45s
            print(f"  rate limited, sleeping {wait}s...")
            time.sleep(wait)
        except APIError as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 * (2 ** attempt)
            print(f"  API error ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("call_llm exhausted retries")