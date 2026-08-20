"""Optional LLM-backed classifier, used only to audit the rule-based one.

The rule-based classifier (pipeline/taxonomy.py) is the pipeline's default
and is what score.py/brief.py run on -- it needs no API key and is fully
deterministic, which matters for "re-runnable" in a context where whoever
re-runs this may not have credentials. This module exists to answer a
narrower question: on reviews with no keyword hits ("other_negative"),
would an LLM assign a more specific category? Run it with:

    ANTHROPIC_API_KEY=... python -m pipeline.classify_llm

It samples up to --n uncategorized reviews, classifies them with Claude
against the exact same taxonomy, and writes a disagreement report to
data/classified/llm_audit.json. See docs/ai_work_log.md for what this run
actually found.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .classify import CLASSIFIED_PATH
from .taxonomy import CATEGORIES

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO_ROOT / "data" / "classified" / "llm_audit.json"

SYSTEM_PROMPT = f"""You are classifying a single mobile-game app store review into
exactly one of these categories: {", ".join(CATEGORIES)}, other_negative.

Definitions:
- bug_crash: app crashes, freezes, won't load, technical malfunction
- monetization: complaints about price, ads, in-app purchases, pay-to-win
- account_support: login/account issues, lost progress, customer support
- gameplay_balance: matchmaking, difficulty, fairness, AI opponents
- performance: lag, battery drain, load times, storage size
- onboarding_ux: confusing UI/tutorial/navigation
- content_feature_request: asking for new features/modes/content
- praise: general positive review with no specific actionable complaint
- other_negative: negative but doesn't fit any category above

Reply with ONLY the category name, nothing else."""


def classify_one(client, model: str, title: str, body: str, rating: int) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=20,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Rating: {rating}/5\nTitle: {title}\nBody: {body}"}],
    )
    return msg.content[0].text.strip()


def run(n: int = 40, model: str = "claude-haiku-4-5-20251001"):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set -- this audit step is optional, skipping is fine.")
    import anthropic  # imported lazily so the rest of the pipeline never needs this dependency

    client = anthropic.Anthropic()
    with open(CLASSIFIED_PATH, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    sample = [r for r in rows if r["category"] == "other_negative"][:n]
    disagreements = []
    for r in sample:
        llm_cat = classify_one(client, model, r.get("title", ""), r["body"], r["rating"])
        if llm_cat != r["category"]:
            disagreements.append({
                "app_key": r["app_key"], "rating": r["rating"], "body": r["body"][:300],
                "rule_based": r["category"], "llm": llm_cat,
            })

    out = {"sampled": len(sample), "disagreements": disagreements}
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"audited {len(sample)} reviews, {len(disagreements)} disagreements -> {AUDIT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = parser.parse_args()
    run(n=args.n, model=args.model)
