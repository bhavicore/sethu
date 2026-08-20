"""Turns classified reviews into one priority number per category, for the
target app only (competitors are only used as a comparison signal, see
`gap` below -- we're not ranking their backlog, we're using them to tell
whether a Hitwicket problem is a genre-wide tax or a Hitwicket-specific one).

The five inputs, and why each is in the formula (full paragraph defense in
docs/scoring.md):

  volume   - how many players hit this. Bigger blast radius, fix it first.
  severity - how angry they are (low star rating). A 1-star crash report
             outranks a 3-star crash report; same category, different heat.
  recency  - is this still happening, or did we already fix it. A category
             that was bad 80 days ago and quiet since shouldn't outrank one
             that's live this week.
  trend    - is it getting worse week over week. Catches emerging fires
             before volume alone would flag them.
  gap      - is Hitwicket worse than its competitors here, proportionally.
             A category every sports game gets complaints about is a lower
             lever than one where Hitwicket is the outlier.

Weights: volume 0.30, severity 0.25, recency 0.15, trend 0.15, gap 0.15.
Volume and severity dominate on purpose -- "how many, how mad" is the
closest single-number proxy for player-facing damage; recency/trend/gap
are lower-weighted modifiers that reorder near-ties, not overrides.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from .classify import CLASSIFIED_PATH
from .scrape import load_config
from .taxonomy import CATEGORIES, OWNER

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORES_PATH = REPO_ROOT / "data" / "classified" / "scores.json"

RANKED_CATEGORIES = [c for c in CATEGORIES if c != "praise"] + ["other_negative"]
WEIGHTS = {"volume": 0.30, "severity": 0.25, "recency": 0.15, "trend": 0.15, "gap": 0.15}
RECENCY_HALFLIFE_DAYS = 14


def _load_reviews() -> list[dict]:
    if not CLASSIFIED_PATH.exists():
        return []
    with open(CLASSIFIED_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _minmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-9:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _recency_weight(review_date: str, now: dt.datetime) -> float:
    d = dt.datetime.fromisoformat(review_date)
    days_ago = max((now - d).days, 0)
    return 0.5 ** (days_ago / RECENCY_HALFLIFE_DAYS)


def score(window_days: int | None = None) -> dict:
    cfg = load_config()
    window_days = window_days or cfg["window_days"]
    all_reviews = _load_reviews()
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=window_days)

    def in_window(r):
        return dt.datetime.fromisoformat(r["date"]) >= cutoff

    windowed = [r for r in all_reviews if in_window(r)]

    target_key = next(a["key"] for a in cfg["apps"] if a["is_target"])
    competitor_keys = [a["key"] for a in cfg["apps"] if not a["is_target"]]

    target_reviews = [r for r in windowed if r["app_key"] == target_key]
    competitor_reviews = {k: [r for r in windowed if r["app_key"] == k] for k in competitor_keys}

    volume, severity, recency, trend, gap = {}, {}, {}, {}, {}
    week1_cut = now - dt.timedelta(days=7)
    week2_cut = now - dt.timedelta(days=14)
    target_total = max(len(target_reviews), 1)

    for cat in RANKED_CATEGORIES:
        cat_reviews = [r for r in target_reviews if r["category"] == cat]
        volume[cat] = len(cat_reviews)
        severity[cat] = (sum(6 - r["rating"] for r in cat_reviews) / len(cat_reviews)) if cat_reviews else 0.0
        recency[cat] = (sum(_recency_weight(r["date"], now) for r in cat_reviews) / len(cat_reviews)) if cat_reviews else 0.0

        this_week = sum(1 for r in cat_reviews if dt.datetime.fromisoformat(r["date"]) >= week1_cut)
        last_week = sum(1 for r in cat_reviews if week2_cut <= dt.datetime.fromisoformat(r["date"]) < week1_cut)
        trend[cat] = (this_week - last_week) / max(last_week, 1)

        hitwicket_share = len(cat_reviews) / target_total
        comp_shares = []
        for k in competitor_keys:
            comp_total = max(len(competitor_reviews[k]), 1)
            comp_cat = sum(1 for r in competitor_reviews[k] if r["category"] == cat)
            comp_shares.append(comp_cat / comp_total)
        comp_avg_share = sum(comp_shares) / len(comp_shares) if comp_shares else 0.0
        gap[cat] = hitwicket_share - comp_avg_share

    volume_n, severity_n, recency_n, trend_n, gap_n = (
        _minmax(volume), _minmax(severity), _minmax(recency), _minmax(trend), _minmax(gap)
    )

    results = []
    for cat in RANKED_CATEGORIES:
        priority = (
            WEIGHTS["volume"] * volume_n.get(cat, 0)
            + WEIGHTS["severity"] * severity_n.get(cat, 0)
            + WEIGHTS["recency"] * recency_n.get(cat, 0)
            + WEIGHTS["trend"] * trend_n.get(cat, 0)
            + WEIGHTS["gap"] * gap_n.get(cat, 0)
        )
        results.append({
            "category": cat,
            "owner": OWNER.get(cat, "Needs manual triage"),
            "priority_score": round(priority, 4),
            "volume": volume[cat],
            "avg_rating_in_category": round(5 - severity[cat] + 1, 2) if volume[cat] else None,
            "wow_trend_pct": round(trend[cat] * 100, 1),
            "hitwicket_vs_competitor_gap_pp": round(gap[cat] * 100, 1),
        })
    results.sort(key=lambda r: r["priority_score"], reverse=True)

    out = {
        "generated_at": now.isoformat(),
        "window_days": window_days,
        "target_app": target_key,
        "target_reviews_in_window": len(target_reviews),
        "competitor_reviews_in_window": {k: len(v) for k, v in competitor_reviews.items()},
        "weights": WEIGHTS,
        "ranking": results,
    }
    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"scored {len(RANKED_CATEGORIES)} categories -> {SCORES_PATH}")
    return out


if __name__ == "__main__":
    score()
