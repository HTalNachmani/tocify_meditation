"""Claude triage backend. Needs ANTHROPIC_API_KEY. Model via ANTHROPIC_MODEL env.

Structured output is obtained by forcing one tool call whose input_schema is SCHEMA.
This is a long-stable Messages API feature (no beta headers, no newer output-format
parameters), so the backend depends on as little of the API surface as possible.
"""

import os
import time

import anthropic

from integrations._shared import SCHEMA, build_triage_prompt

SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", "500"))
MAX_OUTPUT_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "16000"))
# Override with the ANTHROPIC_MODEL env var (the workflow reads it from a repo variable).
DEFAULT_MODEL = "claude-sonnet-5"
TOOL_NAME = "submit_triage"


def make_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    # The SDK retries connection errors, 429s and 5xx with backoff on its own.
    return anthropic.Anthropic(api_key=key, max_retries=6, timeout=300.0)


def _reconcile(result: dict, items: list[dict]) -> dict:
    """Trust the model only for score/why/tags. Titles, links etc. are copied from our own
    items by id, so a garbled link or invented id can never reach digest.md."""
    by_id = {it["id"]: it for it in items}
    ranked = []
    for r in result.get("ranked", []):
        it = by_id.get(r.get("id"))
        if it is None:
            continue  # id not in this batch: hallucinated or mangled
        try:
            score = min(1.0, max(0.0, float(r.get("score"))))
        except (TypeError, ValueError):
            continue
        ranked.append(
            {
                "id": it["id"],
                "title": it["title"],
                "link": it["link"],
                "source": it["source"],
                "published_utc": it.get("published_utc"),
                "score": score,
                "why": str(r.get("why") or "").strip(),
                "tags": [str(t) for t in (r.get("tags") or [])],
            }
        )
    notes = str(result.get("notes") or "")
    missing = len(items) - len({r["id"] for r in ranked})
    if missing:
        print(f"WARNING: model returned no usable score for {missing} of {len(items)} items")
        notes = (notes + f" [{missing} of {len(items)} items in this batch were not scored by the model.]").strip()
    return {"week_of": result.get("week_of", ""), "notes": notes, "ranked": ranked}


def call_claude_triage(client: anthropic.Anthropic, interests: dict, items: list[dict]) -> dict:
    model = os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL
    prompt, _ = build_triage_prompt(interests, items, summary_max_chars=SUMMARY_MAX_CHARS)
    tool = {
        "name": TOOL_NAME,
        "description": "Submit the ranked triage of the RSS items.",
        "input_schema": SCHEMA,
    }

    last = None
    for attempt in range(3):
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            tools=[tool],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "max_tokens":
            # Retrying the same batch would truncate again.
            raise RuntimeError(
                f"Claude output hit max_tokens={MAX_OUTPUT_TOKENS}; lower BATCH_SIZE or raise ANTHROPIC_MAX_TOKENS."
            )
        for block in resp.content:
            if block.type == "tool_use" and block.name == TOOL_NAME and isinstance(block.input, dict):
                if isinstance(block.input.get("ranked"), list):
                    return _reconcile(block.input, items)
        last = ValueError("Claude response had no usable submit_triage tool call")
        time.sleep(2)
    raise last
