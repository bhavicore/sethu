# AI work log

## What was used

This entire pipeline — scraper, taxonomy, scoring, brief renderer, tests,
GitHub Actions workflow, and this doc — was built by **Claude (Sonnet 5),
via Claude Code**, working from a single instruction ("do the AI track")
plus the challenge brief itself. No other AI tool or model was used.

## Best prompts, verbatim

**1. Finding the real app identifiers** (web search, not hand-guessed —
the challenge doc names competitors "Tennis Clash" and "Baseball Clash"
for the non-AI track but never gives package/app-store IDs for any of the
three apps):

```
Hitwicket Superstars Google Play Store package name app id
Tennis Clash Baseball Clash Google Play Store package name
Hitwicket cricket game Apple App Store id apps.apple.com
Tennis Clash Baseball Clash Apple App Store app id apps.apple.com
```

**2. The classification prompt** used by the optional LLM audit pass
(`pipeline/classify_llm.py`), which checks the rule-based classifier's
`other_negative` bucket against Claude's judgment:

```
You are classifying a single mobile-game app store review into
exactly one of these categories: bug_crash, monetization, account_support,
gameplay_balance, performance, onboarding_ux, content_feature_request,
praise, other_negative.

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

Reply with ONLY the category name, nothing else.
```

## Where the AI was confidently wrong

Writing `pipeline/taxonomy.py`'s tie-break rule, I also wrote a test
asserting that `"there's a bug, please add a fix"` would produce a 1-1 tie
between `bug_crash` and `content_feature_request`, with `bug_crash` winning
on priority order. I was confident this was a clean tie-break example.

It wasn't. `pytest` failed: the review actually scored `bug_crash: 1` but
`content_feature_request: 2`, because two of that category's regex
patterns — `r"please add"` and `r"add (a |an |more |the )?"` — both match
the same phrase "please add a", so a single mention of "add" silently
double-counts. I'd designed the keyword lists by eyeballing them for
*coverage* (does some pattern catch this phrasing) and never checked them
for *overlap* (does more than one pattern catch the same phrasing), so my
mental model of the scoring — "one hit per category per distinct concept
mentioned" — was wrong; it's actually "one hit per matching pattern," and
some categories have redundant patterns.

I caught it because the test failed, not because I re-read the regex list
and spotted it — I would not have noticed by inspection. The fix was in
the test, not the code: I picked genuinely non-overlapping single-pattern
keywords (`"scam"` for monetization, `"ui"` for onboarding_ux) to test the
tie-break logic itself, and left the classifier's keyword lists as-is,
since overlap within one category only ever pushes that category's own
count up — it can't cause it to steal a *tie* it wouldn't otherwise be
competitive for, so it doesn't undermine the tie-break rule, only my first
attempt at demonstrating it. It's still worth knowing about: it means
`hit_counts` isn't literally "distinct issues mentioned," it's "pattern
matches," which is documented as a limitation in `docs/taxonomy.md`'s
methodology note for anyone extending the keyword lists later.
