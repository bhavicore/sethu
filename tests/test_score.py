import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.score import _minmax, _recency_weight
import datetime as dt


def test_minmax_handles_equal_values():
    assert _minmax({"a": 3, "b": 3}) == {"a": 0.5, "b": 0.5}


def test_minmax_basic_range():
    out = _minmax({"a": 0, "b": 5, "c": 10})
    assert out["a"] == 0.0
    assert out["c"] == 1.0
    assert out["b"] == 0.5


def test_recency_weight_decays_with_age():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.isoformat()
    two_weeks_ago = (now - dt.timedelta(days=14)).isoformat()
    assert _recency_weight(today, now) > _recency_weight(two_weeks_ago, now)
    # half-life is 14 days, so ~0.5 there
    assert abs(_recency_weight(two_weeks_ago, now) - 0.5) < 0.05
