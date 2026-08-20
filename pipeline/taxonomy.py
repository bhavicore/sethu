"""The review taxonomy: 8 categories, each mapped to a single owner inside a
small game studio. That's the design principle (see docs/taxonomy.md for the
full justification) -- a taxonomy is only useful to a founder if every
category tells you who should look at it next.

Classification is rule-based (regex keyword matching) by default: zero
dependencies, deterministic, runs identically on any machine with no API
key. An optional LLM backend (classify_llm) is provided for higher recall
on reviews that use no matching keywords -- see pipeline/classify_llm.py
and docs/ai_work_log.md for where the two disagree and why the rule-based
version is the default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Priority order matters for tie-breaking: when a review matches two
# categories equally, the more actionable / more severe one wins, so a
# crash complaint that also grumbles about ads gets filed as a crash, not
# buried as a monetization gripe.
CATEGORIES = [
    "bug_crash",
    "monetization",
    "account_support",
    "gameplay_balance",
    "performance",
    "onboarding_ux",
    "content_feature_request",
    "praise",
]

OWNER = {
    "bug_crash": "Engineering / QA",
    "monetization": "Product + Economy design",
    "account_support": "Player Ops / CS",
    "gameplay_balance": "Game design",
    "performance": "Engineering (perf)",
    "onboarding_ux": "Product design / UX",
    "content_feature_request": "Product (roadmap)",
    "praise": "None -- signal only",
}

KEYWORDS: dict[str, list[str]] = {
    "bug_crash": [
        r"crash(es|ed|ing)?", r"freez(e|es|ing|ed)", r"\bbug(s|gy)?\b", r"glitch",
        r"force ?close", r"won'?t (open|load|start)", r"not working", r"stuck on",
        r"black screen", r"white screen", r"error( code)?", r"doesn'?t (open|load|work)",
        r"keeps? closing", r"app closes",
    ],
    "monetization": [
        r"pay to win", r"\bp2w\b", r"(too |very )?expensive", r"overpriced", r"price(y|s|ing)?",
        r"\bads?\b", r"advertisement", r"in-?app purchase", r"\biap\b", r"scam",
        r"refund", r"subscription", r"gems?\b", r"coins?\b", r"real money",
        r"waste(d)? (of )?money", r"micro ?transaction", r"cash grab",
    ],
    "account_support": [
        r"log ?in", r"sign ?in", r"account", r"lost (my )?(progress|data|account)",
        r"customer (service|support)", r"\bban(ned)?\b", r"restore (my )?purchase",
        r"password", r"support (team|ticket|response)?", r"no reply", r"never respond",
    ],
    "gameplay_balance": [
        r"unfair", r"match ?making", r"\bbot(s)?\b", r"ai opponent", r"difficult(y)?",
        r"(un)?balanc(e|ed|ing)", r"overpowered", r"\bop\b", r"nerf", r"buff",
        r"rigged", r"algorithm", r"cheat(ing|er|s)?", r"unrealistic",
    ],
    "performance": [
        r"\blag(gy|ging)?\b", r"\bslow\b", r"loading( time)?", r"battery",
        r"overheat", r"\bfps\b", r"data usage", r"buffer(ing)?", r"storage (space|size)",
        r"large (size|file)",
    ],
    "onboarding_ux": [
        r"confus(ing|ed)", r"tutorial", r"\bui\b", r"interface", r"hard to (understand|use|navigate)",
        r"navigat(e|ion)", r"\bmenu\b", r"instructions", r"(don'?t|can'?t) (understand|figure out)",
        r"complicated",
    ],
    "content_feature_request": [
        r"please add", r"wish (it|there|you)", r"should have", r"need more",
        r"\bfeature\b", r"new mode", r"tournament", r"\bleague\b", r"customi[sz]ation",
        r"add (a |an |more |the )?", r"would be (nice|great|good) if", r"suggestion",
    ],
    "praise": [
        r"\blove\b", r"\bgreat\b", r"amazing", r"best game", r"awesome", r"\bfun\b",
        r"addictive", r"good game", r"excellent", r"perfect", r"recommend",
        r"favorite", r"favourite", r"\bnice\b", r"enjoy(ing|able)?",
    ],
}

_COMPILED = {
    cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in KEYWORDS.items()
}


@dataclass
class Classification:
    primary: str
    matched: list[str]      # all categories with >=1 keyword hit
    hit_counts: dict[str, int]


def classify(title: str, body: str, rating: int) -> Classification:
    text = f"{title} {body}"
    hit_counts: dict[str, int] = {}
    for cat in CATEGORIES:
        n = sum(1 for pat in _COMPILED[cat] if pat.search(text))
        if n:
            hit_counts[cat] = n

    if not hit_counts:
        # No keyword fired. Fall back to star rating as a coarse signal:
        # low-star silence still means *something* is wrong even if the
        # reviewer didn't use a word we recognize.
        primary = "praise" if rating >= 4 else "other_negative"
        return Classification(primary=primary, matched=[], hit_counts={})

    max_hits = max(hit_counts.values())
    tied = [c for c in CATEGORIES if hit_counts.get(c) == max_hits]
    primary = tied[0]  # CATEGORIES is already priority-ordered
    return Classification(primary=primary, matched=list(hit_counts), hit_counts=hit_counts)
