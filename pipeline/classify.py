"""Applies the taxonomy to every raw review and writes one classified table.

Reads data/raw/<app_key>.ndjson (written by scrape.py), classifies each
review, and writes data/classified/reviews.ndjson -- the single input the
scoring and brief steps consume. Re-running this after a fresh scrape just
re-classifies the (now larger) raw set; classification is a pure function
of the review text, so it's always safe to redo in full and cheap enough
(regex, no network) that we don't bother trying to diff it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .scrape import RAW_DIR, load_config
from .taxonomy import classify as classify_text

REPO_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIED_DIR = REPO_ROOT / "data" / "classified"
CLASSIFIED_PATH = CLASSIFIED_DIR / "reviews.ndjson"


def run() -> int:
    cfg = load_config()
    CLASSIFIED_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(CLASSIFIED_PATH, "w", encoding="utf-8") as out:
        for app in cfg["apps"]:
            raw_path = RAW_DIR / f"{app['key']}.ndjson"
            if not raw_path.exists():
                continue
            with open(raw_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    c = classify_text(row.get("title", ""), row.get("body", ""), row["rating"])
                    row["category"] = c.primary
                    row["matched_categories"] = c.matched
                    out.write(json.dumps(row) + "\n")
                    n += 1
    print(f"classified {n} reviews -> {CLASSIFIED_PATH}")
    return n


if __name__ == "__main__":
    run()
