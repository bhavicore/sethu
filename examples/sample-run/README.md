# Sample run (synthetic data)

The `raw/*.ndjson` files in this folder are **synthetic, hand-generated
reviews**, not scraped data — generated locally to sanity-check that
classify → score → brief runs end-to-end and produces a sane, readable
brief before spending the real scrape run against the live stores (which
this sandboxed dev environment couldn't reach directly; see the repo
README's "Network note").

`briefs/2026-08-19.md` is the brief that synthetic data produced — kept
here purely as a worked example of the output shape. **It is not a real
Hitwicket review brief.** The real brief, generated from an actual
Google Play / App Store scrape via the GitHub Actions workflow, lives in
`data/briefs/` at the repo root once that workflow has run.
