# Priority scoring

For each category (excluding `praise`), we compute one number, 0–1, and
rank categories by it. Formula:

```
priority = 0.30 · volume + 0.25 · severity + 0.15 · recency + 0.15 · trend + 0.15 · gap
```

Every component is min-max normalized across categories *within that run*
(so "volume" isn't raw review count, it's "how does this category's volume
compare to the other categories this week"). That keeps the score
comparable across weeks even as total review volume drifts.

| Component | What it measures | How it's computed |
|---|---|---|
| `volume` | How many players hit this | Count of reviews in the category, in-window |
| `severity` | How angry they are | Mean of `(6 − star rating)` for reviews in the category — a 1★ review contributes 5, a 5★ contributes 1 |
| `recency` | Is this still happening | Mean of an exponential decay per review, half-life 14 days — a review from today counts ~1.0, one from 28 days ago counts ~0.25 |
| `trend` | Is it getting worse | `(this week's count − last week's count) / max(last week's count, 1)` |
| `gap` | Is Hitwicket worse than peers here | Hitwicket's share of its own reviews in this category, minus the average share for Tennis Clash and Baseball Clash in the same category, same window |

## Weights, defended

**Volume (0.30) and severity (0.25) carry more than half the score on
purpose.** "How many people hit this, and how mad are they" is the closest
single-number proxy we have for actual player-facing damage, and it's the
one a founder would ask for first if they could only ask one question.
Recency (0.15) and trend (0.15) are deliberately lower-weighted — they're
there to break near-ties in favor of what's *live* over what's *historical*,
not to override a high-volume, high-severity category just because it
happens to be a week old. Gap (0.15) is the smallest weight because it's
the least reliable signal: competitor review volume is smaller and noisier
than Hitwicket's own (fewer India-region reviews for two Western-published
titles), so we let it nudge the ranking rather than dominate it.

**What we chose not to weight:** raw star rating alone (too coarse — a
1-star "meh, boring" and a 1-star "crashes on launch" are very different
actions), and reviewer helpfulness/upvotes (neither store's public API
surfaces this reliably enough to trust).

## Why not just sort by volume

Because the brief exists to catch things *before* they're the biggest
bucket, not just report what already is. A category with 15 reviews this
week, up from 3 last week, all 1-star, all posted today, is a fire — even
if `content_feature_request` has 40 reviews total. That's what
recency+trend are for: they let a small, sharp, fresh spike outrank a
large, flat, stale bucket near the margin, without ever letting it beat a
bucket that's also large and severe (volume+severity are still 55% of the
score).

## Re-running

Scores are recomputed from scratch every run (`pipeline/score.py`) from
whatever's in `data/classified/reviews.ndjson` at that moment — nothing is
cached or incremental at the scoring layer, only the scrape step dedupes.
That means two runs a week apart produce two independently-computed,
directly-comparable rankings, which is what "week over week" in `trend`
and the brief itself actually depends on.
