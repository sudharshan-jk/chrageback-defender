\# ChargebackDefender



An AI agent that reads a chargeback notice, figures out whether the merchant has enough evidence to win, and if so, writes a representment letter grounded in that evidence. If the evidence isn't there, it says so — and explains why fighting would waste the merchant's one shot at responding.



Razorpay AI Buildathon · Track: AI Risk Manager



\---



\## Why this matters



A chargeback gives the merchant 30 days (Visa) or 45 days (Mastercard) to respond. Miss that window and the money is gone automatically. Most merchants either ignore the notice or paste a generic letter that says "we dispute this charge" without addressing what the network actually asked for. Both responses lose.



The harder problem is knowing when not to fight. A merchant gets one response per dispute. Filing a weak representment doesn't just fail — it burns the only chance they had to submit a stronger one later. The system needs to say "don't fight this" when the evidence isn't there, and mean it.



\## What it does



1\. Reads the chargeback notice and identifies the reason code, network, amounts, and deadlines

2\. Looks up what evidence Visa or Mastercard requires for that specific reason code

3\. Calls the merchant's systems (order data, delivery tracking, customer emails, transaction signals) to see what evidence actually exists

4\. Scores winnability: what fraction of the required evidence is present

5\. If the evidence is there, writes a letter citing each piece. If it isn't, recommends accepting and explains the gap



Every factual claim in the letter is tagged with where it came from — either a tool call or a network rule. Claims without valid citations get stripped. If too many get stripped, the whole letter is thrown out and replaced with a safe template.



\## Numbers



50 synthetic disputes, each with a known ground truth (winnable or not, based on whether the required evidence exists in the mock merchant data). The baseline is a template that always fights and ignores evidence.



| Metric | Baseline | Agent |

|---|---:|---:|

| Triage accuracy (fight vs accept) | 18.0% | 100.0% |

| Letter quality (0–10, Gemini judge) | 2.00 | 5.21 |



| Agent-only metric | Value |

|---|---:|

| Fallback rate | 18.0% |

| Claims stripped by validation | 1.7% |

| Expensive-model calls skipped by triage | 10.0% |

| Median latency | 10.5s |

| p95 latency | 66.3s |



The 100% triage number is expected, not remarkable. Triage is deterministic — it computes winnability from tool outputs and compares against a threshold calibrated to match the ground truth definition. It shows the wiring is correct. The letter quality score is where the LLM earns its place: the agent's letters averaged 5.21 against the baseline's 2.00, judged by Gemini 3.6 Flash (a different model family from the one that wrote them).



Reproduce: `uv run python -m src.eval.run\_eval 50` then `uv run python -m src.eval.report`.



\## How it works



```

notice text

&#x20;   │

&#x20;   ▼

classify (gpt-oss-20b, fast)

&#x20;   │   extracts reason\_code, network, IDs, amount

&#x20;   │   retrieval pulls the top-5 matching codes from a 42-code corpus

&#x20;   ▼

gather (deterministic, no LLM)

&#x20;   │   maps required\_evidence → merchant tools

&#x20;   │   calls 6 tools, collects what's present and what's missing

&#x20;   │   winnability = present / gatherable

&#x20;   ▼

route

&#x20;   ├── < 0.60         → ACCEPT, no letter, no expensive model call

&#x20;   ├── 0.60 to 0.99   → draft letter, flag for merchant review

&#x20;   └── ≥ 0.99         → draft letter, mark ready to send

&#x20;                            │

&#x20;                       draft (gpt-oss-120b, slow)

&#x20;                            │

&#x20;                       validate (deterministic)

&#x20;                            │

&#x20;                       ├── pass → ship the letter

&#x20;                       └── fail → template fallback

```



\## Why these choices



\*\*Two models instead of one.\*\* Classification is picking from a known list — a small model handles it. Letter drafting is open-ended argument construction — a larger model writes better ones. Triage sits between them and prevents the expensive call on cases that can't be won. In the eval, 10% of drafting calls were skipped this way.



\*\*Why AI at all.\*\* Evidence lookup and retry scheduling are rules. Writing a letter that connects specific evidence to specific network requirements, and that can quote a customer's own "Received the package, thanks!" email as a rebuttal to their non-receipt claim — that's where a model earns its cost. A template can list facts. It can't construct an argument.



\*\*Citations are load-bearing, not decorative.\*\* Every claim carries a `tool:` or `rule:` tag. Validation resolves each one against tools that were actually called and codes that exist in the corpus. Strip rate is 1.7% — low because the prompt is explicit about citation format and gets one retry on schema failure.



\*\*Three reason codes, not forty-two.\*\* The corpus holds 42 extracted codes, but the six mock tools cover the evidence requirements of three: Mastercard 4855 (non-receipt), Visa 10.4 (card-absent fraud), and Visa 13.1 (merchandise not received). Building mock tools for the other 39 would have inflated the numbers without testing anything real. Extending coverage means adding tools, not changing the agent.



\*\*Honest evidence accounting.\*\* Each tool returns an `evidence\_provided` list naming exactly which tokens it can vouch for on that specific order. The agent checks membership per token. The ground truth generator uses the same mapping. They measure the same thing, by construction — this took three iterations to get right (see below).



\## What broke during development



\*\*The ground truth and the tools lived in different realities.\*\* The synthetic data generator decided winnability based on abstract flags. The tools returned success if any evidence existed, regardless of which specific type. The agent reported winnability 1.0 on disputes the generator called unwinnable. Sanity check: 0 out of 10 cases agreed.



The fix was making each tool declare exactly which evidence tokens it could back up for that order, and computing winnability only over evidence types the tools can actually gather. After that, agreement went to 10 out of 10.



\*\*Validation penalised the LLM for being right.\*\* The validation layer required every tool that returned data to be cited in the letter. But transaction signals (AVS, CVV, 3DS) are irrelevant to a non-receipt dispute — the question is whether the package arrived, not whether the card authenticated. The LLM skipped the irrelevant tool and got rejected for it. Fixed by only requiring citation of tools whose evidence types intersect the reason code's requirements.



\*\*Rate limits hit during the eval, twice.\*\* Groq throttled on the last 10 cases. The retry logic (5s → 15s → 45s backoff) handled it, and when retries were exhausted, the fallback fired — those cases completed on template letters instead of crashing. The Gemini judge hit its daily quota separately and returned zeros for every sampled case. The production path degraded gracefully because it was designed to. The eval path failed loudly because it wasn't. The asymmetry was accidental but it's the correct one — a production system that crashes is unacceptable; an eval that pauses and retries tomorrow is fine.



\## Running it



Needs Python 3.11+, \[uv](https://docs.astral.sh/uv/), and free API keys from \[Groq](https://console.groq.com) and \[Google AI Studio](https://aistudio.google.com/apikey). No paid access required.



```bash

cp .env.example .env                    # add your two keys

uv sync

uv run python -m src.retrieval          # build the reason-code index

uv run python scripts/generate\_data.py  # generate mock orders + disputes

uv run streamlit run app/main.py        # demo UI

uv run python -m src.eval.run\_eval 50   # full eval (\~18 min)

uv run python -m src.eval.report        # summary table + chart

```



On Windows: `.\\tasks.ps1 \[install|demo|eval|test|clean]`.



\## Stack



| Layer | Tool | Role |

|---|---|---|

| Classification | gpt-oss-20b via Groq | Read the notice, pick the reason code |

| Drafting | gpt-oss-120b via Groq | Write the representment letter |

| Eval judge | gemini-3.6-flash | Score letters (different family from the drafter) |

| Retrieval | ChromaDB + all-MiniLM-L6-v2 | Match notice text to reason codes, local |

| Structured output | Pydantic | Schema enforcement with one retry on violation |

| Corpus | 42 reason codes in JSON | Extracted from Visa/Mastercard public reference material, five hand-verified |

| Demo | Streamlit | One page, three demo cases |



Total cost: ₹0. Built on free tiers throughout. The architecture doesn't depend on frontier models — it would run better on Claude or GPT-4, not differently.



\## What isn't built



No real payment network API (none exists publicly). No PDF parsing for notices. No merchant authentication. No database beyond JSON files. No fine-tuning. No multi-agent framework. Each cut was deliberate — depth in the evidence-and-validation pipeline over breadth in features.



\## What would come next



Learn from actual dispute outcomes instead of a static threshold — if a merchant wins 4855 disputes with tracking data alone, the winnability model should reflect that. Expand tool coverage to more reason codes. Ingest real chargeback PDFs. Add a merchant review queue for the cases the agent flags as "review" rather than "fight" or "accept."





