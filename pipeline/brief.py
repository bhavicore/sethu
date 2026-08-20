"""Renders the weekly brief: the one artifact a founder actually reads.

Design constraint from the challenge brief itself: "a founder reads in 90
seconds and acts on. Not a wall of charts." So this is deliberately one
markdown file, one screen, ranked table + top 3 + one comparison table.
Everything else the pipeline computed (per-review classifications, full
scoring breakdown) stays in data/classified/ for anyone who wants to dig in,
but it is not in the brief.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .classify import CLASSIFIED_PATH
from .score import SCORES_PATH
from .scrape import load_config
from .taxonomy import CATEGORIES

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEFS_DIR = REPO_ROOT / "data" / "briefs"

RECOMMENDED_ACTION = {
    "bug_crash": "Pull crash logs / device+OS breakdown for this window and triage the top 2 crash signatures.",
    "monetization": "Review the last pricing/offer change against this window's complaint volume; check if an offer's frequency or anchor price moved recently.",
    "account_support": "Audit CS response time and login/restore-purchase failure rate for this window.",
    "gameplay_balance": "Have game design review matchmaking/bot-difficulty logs for the affected skill band.",
    "performance": "Profile load time and battery draw on the 2-3 most common device models among complainers.",
    "onboarding_ux": "Watch 3 fresh-install session recordings (or run a 5-user hallway test) against the first-run flow.",
    "content_feature_request": "Cluster the specific asks; this is roadmap input, not a fire -- batch into next planning cycle.",
    "other_negative": "Manually read a sample of 15-20; these reviews didn't match the taxonomy's keywords and may signal a new failure mode.",
}


def _sample_quote(app_key: str, category: str, n: int = 1) -> list[str]:
    quotes = []
    if not CLASSIFIED_PATH.exists():
        return quotes
    with open(CLASSIFIED_PATH) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    candidates = [
        r for r in rows
        if r["app_key"] == app_key and r["category"] == category and r["body"]
    ]
    candidates.sort(key=lambda r: r["date"], reverse=True)
    for r in candidates[:n]:
        body = r["body"].strip().replace("\n", " ")
        if len(body) > 220:
            body = body[:217] + "..."
        quotes.append(f'"{body}" -- {r["rating"]}★, {r["source"]}, {r["date"][:10]}')
    return quotes


def render(window_days: int | None = None) -> Path:
    if not SCORES_PATH.exists():
        raise SystemExit("No scores found -- run pipeline/score.py first.")
    with open(SCORES_PATH) as f:
        scores = json.load(f)
    cfg = load_config()
    target_key = scores["target_app"]
    target_name = next(a["name"] for a in cfg["apps"] if a["key"] == target_key)
    competitor_names = {a["key"]: a["name"] for a in cfg["apps"] if not a["is_target"]}

    generated = dt.datetime.fromisoformat(scores["generated_at"])
    window_days = window_days or scores["window_days"]
    ranking = scores["ranking"]
    top3 = ranking[:3]

    lines: list[str] = []
    lines.append(f"# Weekly Review Brief -- {target_name}")
    lines.append("")
    lines.append(
        f"_Generated {generated.strftime('%Y-%m-%d %H:%M UTC')} "
        f"· {window_days}-day window · "
        f"{scores['target_reviews_in_window']} Hitwicket reviews ingested "
        f"vs {sum(scores['competitor_reviews_in_window'].values())} across "
        f"{len(competitor_names)} competitors_"
    )
    lines.append("")
    lines.append("## In 90 seconds")
    lines.append("")
    if top3:
        lead = top3[0]
        lines.append(
            f"**{lead['category'].replace('_', ' ').title()}** is this week's #1 priority "
            f"(score {lead['priority_score']}, {lead['volume']} reviews, "
            f"{'up' if lead['wow_trend_pct'] > 0 else 'down' if lead['wow_trend_pct'] < 0 else 'flat'} "
            f"{abs(lead['wow_trend_pct'])}% week-over-week). "
            f"Owner: {lead['owner']}."
        )
    lines.append("")
    lines.append("## Fix this week")
    lines.append("")
    for i, item in enumerate(top3, 1):
        cat = item["category"]
        lines.append(f"**{i}. {cat.replace('_', ' ').title()}** -- score {item['priority_score']} "
                      f"· {item['volume']} reviews · owner: {item['owner']}")
        lines.append(f"   - Action: {RECOMMENDED_ACTION.get(cat, 'Manual triage needed.')}")
        for q in _sample_quote(target_key, cat):
            lines.append(f"   - Quote: {q}")
        lines.append("")

    lines.append("## Full ranking")
    lines.append("")
    lines.append("| # | Category | Score | Volume | WoW trend | Avg rating | Gap vs competitors | Owner |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, item in enumerate(ranking, 1):
        gap = item["hitwicket_vs_competitor_gap_pp"] + 0.0  # normalize -0.0 -> 0.0
        gap_str = f"{'+' if gap >= 0 else ''}{gap}pp"
        avg_rating = item["avg_rating_in_category"] if item["avg_rating_in_category"] is not None else "-"
        lines.append(
            f"| {i} | {item['category'].replace('_', ' ').title()} | {item['priority_score']} "
            f"| {item['volume']} | {item['wow_trend_pct']:+.1f}% | {avg_rating} | {gap_str} | {item['owner']} |"
        )
    lines.append("")
    lines.append(
        "_Gap vs competitors = Hitwicket's share of reviews in that category minus the average share "
        "for Tennis Clash and Baseball Clash, in percentage points. Positive means Hitwicket over-indexes "
        "on that complaint relative to genre peers._"
    )
    lines.append("")

    lines.append("## Competitive snapshot")
    lines.append("")
    header = "| Category | " + target_name + " share | " + " share | ".join(competitor_names.values()) + " share |"
    lines.append(header)
    lines.append("|" + "---|" * (len(competitor_names) + 2))
    # recompute shares for display
    if CLASSIFIED_PATH.exists():
        with open(CLASSIFIED_PATH) as f:
            rows = [json.loads(l) for l in f if l.strip()]
        cutoff = generated - dt.timedelta(days=window_days)
        rows = [r for r in rows if dt.datetime.fromisoformat(r["date"]) >= cutoff]
        by_app = {}
        for key in [target_key, *competitor_names]:
            app_rows = [r for r in rows if r["app_key"] == key]
            total = max(len(app_rows), 1)
            by_app[key] = {c: sum(1 for r in app_rows if r["category"] == c) / total for c in CATEGORIES}
        for cat in CATEGORIES:
            cells = [f"{by_app[target_key].get(cat, 0) * 100:.0f}%"]
            for k in competitor_names:
                cells.append(f"{by_app[k].get(cat, 0) * 100:.0f}%")
            lines.append(f"| {cat.replace('_', ' ').title()} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Methodology (recap)")
    lines.append("")
    lines.append(
        "Taxonomy and scoring formula are defined in `docs/taxonomy.md` and `docs/scoring.md`. "
        "Priority = 0.30·volume + 0.25·severity + 0.15·recency + 0.15·trend + 0.15·competitor-gap, "
        "each component min-max normalized across categories for this run. "
        "Re-run with `python -m pipeline.run` -- it only ingests reviews newer than what's already stored."
    )
    lines.append("")

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BRIEFS_DIR / f"{generated.strftime('%Y-%m-%d')}.md"
    out_path.write_text("\n".join(lines))
    latest_path = BRIEFS_DIR / "latest.md"
    latest_path.write_text("\n".join(lines))
    print(f"brief written -> {out_path}")
    return out_path


if __name__ == "__main__":
    render()
