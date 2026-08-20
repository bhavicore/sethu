"""End-to-end entrypoint: scrape -> classify -> score -> brief.

    python -m pipeline.run [--days 90]

Safe to run repeatedly: scraping only appends reviews it hasn't seen
(deduped by review_id), classification and scoring are pure recomputation
from whatever's stored, and the brief overwrites data/briefs/latest.md
plus writes a dated copy so you can diff week over week.
"""
from __future__ import annotations

import argparse

from . import scrape, classify, score, brief


def main():
    parser = argparse.ArgumentParser(description="Run the full review-brief pipeline.")
    parser.add_argument("--days", type=int, default=None, help="Lookback window in days (default: config/apps.yaml window_days)")
    parser.add_argument("--skip-scrape", action="store_true", help="Reuse existing data/raw/*.ndjson instead of hitting the stores again")
    args = parser.parse_args()

    if not args.skip_scrape:
        print("== scrape ==")
        scrape.run(window_days=args.days)
    else:
        print("== scrape (skipped) ==")

    print("== classify ==")
    classify.run()

    print("== score ==")
    score.score(window_days=args.days)

    print("== brief ==")
    out = brief.render(window_days=args.days)
    print(f"\nDone. Brief: {out}")


if __name__ == "__main__":
    main()
