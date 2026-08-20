# Review taxonomy

Eight categories. The organizing principle: **every category maps to exactly
one team that would own fixing it.** A taxonomy that's organized around
*symptoms* (e.g. "1-star reviews", "long reviews", "reviews mentioning
money") doesn't tell a founder who to hand it to. A taxonomy organized
around *root cause / owner* does — that's the only reason it's more useful
to us than raw sentiment or star rating alone.

| Category | Definition | Owner | Example trigger words |
|---|---|---|---|
| `bug_crash` | App is technically broken: crashes, freezes, won't load | Engineering / QA | crash, freeze, glitch, force close, black screen |
| `monetization` | Complaints about price, ads, IAP, pay-to-win perception | Product + Economy design | expensive, pay to win, ads, refund, scam |
| `account_support` | Login, lost progress, CS responsiveness | Player Ops / CS | login, lost my progress, no reply, banned |
| `gameplay_balance` | Fairness, matchmaking, AI/bot difficulty | Game design | unfair, matchmaking, rigged, overpowered |
| `performance` | Works, but slow/laggy/battery-draining | Engineering (perf) | lag, battery, loading, fps |
| `onboarding_ux` | Confusing UI, unclear tutorial/navigation | Product design / UX | confusing, tutorial, hard to understand |
| `content_feature_request` | Explicit asks for new content/modes/features | Product (roadmap) | please add, wish, new mode, tournament |
| `praise` | Positive, no specific actionable complaint | None — tracked as a baseline, not routed anywhere | love, great, addictive |

A ninth bucket, `other_negative`, catches negative reviews that hit no
keyword in any category above. It is intentionally *not* silently folded
into an existing category — a review that doesn't match anything is a
signal the taxonomy itself might be missing something, so it's surfaced
in the brief as "needs manual triage" rather than hidden.

## Why this set of eight, not more or fewer

- **Fewer** (e.g. collapsing `performance` into `bug_crash`) would blur the
  Engineering/QA "make it work" work against the Engineering(perf) "make it
  fast" work — different tickets, often different people, in most studios
  this size.
- **More** (e.g. splitting `monetization` into ads vs. IAP vs. pricing)
  would fragment volume across categories, so nothing gets enough weight to
  crack the top 3 in the priority ranking — the challenge explicitly warns
  against a wall of thinly-sliced charts.
- `praise` is kept as its own category, not discarded, because a category
  going *quiet* on complaints while `praise` volume holds steady is itself
  a useful weekly signal (nothing broke, nobody's mad) even though it
  never appears in "fix this week."

## How classification works

Rule-based keyword matching (`pipeline/taxonomy.py`) is the default and
what the scoring/brief steps run on: a fixed set of regex patterns per
category, case-insensitive, matched against title+body. A review's primary
category is the one with the most keyword hits; ties are broken by a fixed
priority order (bugs and monetization outrank UX and feature requests,
since they're more urgent to act on).

This is a deliberate choice over an LLM-only classifier: it's free,
instant, and — critically for "show it re-running" — produces byte-identical
output on every run with no API key and no rate limit. An optional LLM
audit pass (`pipeline/classify_llm.py`) exists to sanity-check the
`other_negative` bucket against Claude's judgment; see `docs/ai_work_log.md`
for what that audit found and where it disagreed with the rules.

**Known limitation:** `hit_counts` counts *pattern* matches, not distinct
issues mentioned — some categories have more than one regex that can match
the same phrase (e.g. monetization's `pay to win` and `p2w` patterns both
fire on "pay to win, basically p2w"), so a category's hit count isn't a
clean count of separate complaints within one review. This only ever
inflates a category's own count; it doesn't change which category wins a
match, so it doesn't affect classification correctness, but keep it in
mind if you extend the keyword lists and start reasoning about hit counts
as anything more than "did this category match, and how strongly."
