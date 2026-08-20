"""Ingests public app reviews for the target app and its competitors.

Two independent sources, both public and keyless:
  - Google Play: via the `google-play-scraper` library (paginated, newest-first).
  - Apple App Store: via Apple's public RSS "customer reviews" JSON feed.

Every review is normalized to one schema and written as newline-delimited
JSON (append-only, deduped by review_id) so re-running the pipeline never
duplicates a review it already has -- only new reviews since the last run
are added. This is what makes the pipeline "re-runnable": run it twice a
week apart and it just grows the dataset, it doesn't start over.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import requests
import yaml

from google_play_scraper import Sort, reviews as play_reviews

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "apps.yaml"
RAW_DIR = REPO_ROOT / "data" / "raw"


@dataclass
class Review:
    source: str          # "play" | "appstore"
    app_key: str          # e.g. "hitwicket"
    app_name: str
    country: str
    review_id: str
    rating: int
    title: str
    body: str
    date: str             # ISO 8601
    is_target: bool

    def key(self) -> str:
        return f"{self.source}:{self.review_id}"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _cutoff(window_days: int) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=window_days)


def scrape_play(app: dict, country: str, window_days: int) -> list[Review]:
    """Pages newest-first until reviews fall outside the window, or the
    store runs out of reviews for that country -- whichever comes first."""
    out: list[Review] = []
    cutoff = _cutoff(window_days)
    token = None
    for _ in range(50):  # hard cap: ~5000 reviews/app/country, plenty for 90 days
        batch, token = play_reviews(
            app["play_id"],
            lang="en",
            country=country,
            sort=Sort.NEWEST,
            count=200,
            continuation_token=token,
        )
        if not batch:
            break
        stop = False
        for r in batch:
            review_date = r["at"].replace(tzinfo=dt.timezone.utc)
            if review_date < cutoff:
                stop = True
                continue
            out.append(Review(
                source="play",
                app_key=app["key"],
                app_name=app["name"],
                country=country,
                review_id=str(r["reviewId"]),
                rating=int(r["score"]),
                title="",
                body=(r["content"] or "").strip(),
                date=review_date.isoformat(),
                is_target=app["is_target"],
            ))
        if stop or token is None:
            break
        time.sleep(0.3)  # be polite to the endpoint
    return out


def scrape_appstore(app: dict, country: str, window_days: int) -> list[Review]:
    """Apple's RSS review feed returns ~50 reviews/page, up to ~10 pages
    (~500 most recent reviews), sorted most-recent-first. No API key needed."""
    out: list[Review] = []
    cutoff = _cutoff(window_days)
    for page in range(1, 11):
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"page={page}/id={app['appstore_id']}/sortby=mostrecent/json"
        )
        resp = requests.get(url, timeout=20, headers={"User-Agent": "review-brief-pipeline/1.0"})
        if resp.status_code != 200:
            break
        try:
            entries = resp.json()["feed"].get("entry", [])
        except (KeyError, ValueError):
            break
        if not entries:
            break
        # First entry on page 1 is the app itself, not a review, when there
        # are no reviews at all -- guard with .get() below rather than assuming.
        stop = False
        for e in entries:
            if "im:rating" not in e:
                continue  # the app-summary pseudo-entry
            review_date_raw = e.get("updated", {}).get("label")
            if not review_date_raw:
                continue
            review_date = dt.datetime.fromisoformat(review_date_raw.replace("Z", "+00:00"))
            if review_date < cutoff:
                stop = True
                continue
            out.append(Review(
                source="appstore",
                app_key=app["key"],
                app_name=app["name"],
                country=country,
                review_id=str(e["id"]["label"]),
                rating=int(e["im:rating"]["label"]),
                title=(e.get("title", {}).get("label") or "").strip(),
                body=(e.get("content", {}).get("label") or "").strip(),
                date=review_date.isoformat(),
                is_target=app["is_target"],
            ))
        if stop:
            break
        time.sleep(0.3)
    return out


def _raw_path(app_key: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / f"{app_key}.ndjson"


def _load_existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids.add(json.loads(line)["_key"])
    return ids


def append_new_reviews(app_key: str, new_reviews: Iterable[Review]) -> int:
    path = _raw_path(app_key)
    existing = _load_existing_ids(path)
    added = 0
    with open(path, "a", encoding="utf-8") as f:
        for r in new_reviews:
            if r.key() in existing:
                continue
            row = asdict(r)
            row["_key"] = r.key()
            f.write(json.dumps(row) + "\n")
            existing.add(r.key())
            added += 1
    return added


def run(window_days: int | None = None) -> dict:
    cfg = load_config()
    window_days = window_days or cfg["window_days"]
    summary = {}
    for app in cfg["apps"]:
        collected: list[Review] = []
        for country in cfg["play_countries"]:
            try:
                collected += scrape_play(app, country, window_days)
            except Exception as e:  # store outage / rate limit for one country shouldn't kill the run
                print(f"[warn] play scrape failed for {app['key']}/{country}: {e}")
        for country in cfg["appstore_countries"]:
            try:
                collected += scrape_appstore(app, country, window_days)
            except Exception as e:
                print(f"[warn] appstore scrape failed for {app['key']}/{country}: {e}")
        added = append_new_reviews(app["key"], collected)
        total = len(_load_existing_ids(_raw_path(app["key"])))
        summary[app["key"]] = {"fetched_this_run": len(collected), "new": added, "total_stored": total}
        print(f"{app['key']}: fetched {len(collected)}, {added} new, {total} total stored")
    return summary


if __name__ == "__main__":
    run()
