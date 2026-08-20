import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.taxonomy import classify


def test_crash_review_classified_as_bug_crash():
    c = classify("", "The app keeps crashing every time I open a match, so frustrating", 1)
    assert c.primary == "bug_crash"


def test_monetization_review():
    c = classify("Too expensive", "This game is pay to win, the gems are way overpriced", 2)
    assert c.primary == "monetization"


def test_positive_review_with_no_keywords_falls_back_to_praise():
    c = classify("", "Been playing every day, really solid", 5)
    assert c.primary == "praise"


def test_negative_review_with_no_keywords_falls_back_to_other_negative():
    c = classify("", "Ugh, whatever, meh", 1)
    assert c.primary == "other_negative"
    assert c.matched == []


def test_tie_break_prefers_monetization_over_onboarding_ux():
    # exactly one keyword hit each ("scam" vs "ui"); priority order picks monetization
    c = classify("", "this is a scam and the ui is bad", 2)
    assert c.hit_counts.get("monetization") == 1
    assert c.hit_counts.get("onboarding_ux") == 1
    assert c.primary == "monetization"
