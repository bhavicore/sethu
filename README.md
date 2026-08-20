# Hitwicket review brief pipeline

Task 2, Option 1 (AI Track) of the Hitwicket Founder's Office Challenge:
a re-runnable pipeline that ingests public app store reviews for Hitwicket
and two competitors (Tennis Clash, Baseball Clash — the same pair used in
this challenge's own non-AI track), classifies them, scores what to fix
first, and renders a weekly brief a founder can read in 90 seconds.

## How it works

```
pipeline/scrape.py    -> data/raw/<app>.ndjson          (Google Play + Apple RSS, keyless, deduped by review_id)
pipeline/classify.py  -> data/classified/reviews.ndjson  (rule-based taxonomy, see docs/taxonomy.md)
pipeline/score.py     -> data/classified/scores.json     (priority ranking, see docs/scoring.md)
pipeline/brief.py     -> data/briefs/<date>.md, latest.md (the actual deliverable)
```

Run all four steps:

```
pip install -r requirements.txt
python -m pipeline.run              # full run, ~90 day window
python -m pipeline.run --days 30    # shorter window
python -m pipeline.run --skip-scrape   # reuse existing data/raw, re-classify/score/brief only
```

Every step is idempotent. `scrape.py` only appends reviews it hasn't seen
(deduped by `review_id`); `classify.py` and `score.py` fully recompute from
whatever's stored, which is what makes `trend` (week-over-week) and the
brief itself directly comparable between two runs a week apart.

## Network note

This pipeline was built inside a sandboxed dev session whose egress policy
blocks direct HTTPS to `play.google.com` / `apps.apple.com` (only a small
allowlist — pypi, npm, github, anthropic — is open). Rather than hand-copy
reviews to fake a working scraper, the actual scrape runs via
`.github/workflows/weekly-review-brief.yml` on a GitHub Actions runner
(which has open internet), commits `data/` back to this branch, and can be
re-triggered on demand (`workflow_dispatch`) or weekly (`schedule`). That's
also the "show it working on a second run" proof: two runs of that workflow
a week apart, both in the Actions history, both producing a comparable
brief with real `trend` numbers.

## Taxonomy and scoring

Eight categories, each mapped to one team that owns fixing it — see
[`docs/taxonomy.md`](docs/taxonomy.md). Priority score is
`0.30·volume + 0.25·severity + 0.15·recency + 0.15·trend + 0.15·competitor-gap`,
defended in [`docs/scoring.md`](docs/scoring.md).

## AI work log

[`docs/ai_work_log.md`](docs/ai_work_log.md) — tools used, best prompts,
and the one place the AI (this pipeline's LLM audit pass) was confidently
wrong.

## Tests

```
python -m pytest tests/
```

Covers the taxonomy classifier's category assignment and tie-breaking, and
the scoring math (min-max normalization, recency decay).

## Sample output

[`examples/sample-run/`](examples/sample-run/) has a worked example built
from synthetic reviews, generated to sanity-check the classify → score →
brief chain before running the real scrape. It is clearly not real
Hitwicket data — see the note in that folder. The real brief, once the
Actions workflow has run against live reviews, lands in `data/briefs/`.
