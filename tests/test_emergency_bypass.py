import pytest

from workout_gate.gate.emergency_bypass import BYPASS_CATEGORIES, HoldToConfirm


def test_not_ready_before_duration():
    h = HoldToConfirm(10)
    h.start(0.0)
    p = h.progress(5.0)
    assert p.holding is True
    assert p.ready is False
    assert 4.9 < p.remaining < 5.1


def test_ready_after_duration():
    h = HoldToConfirm(10)
    h.start(0.0)
    assert h.progress(10.0).ready is True


def test_cancel_resets():
    h = HoldToConfirm(10)
    h.start(0.0)
    h.cancel()
    p = h.progress(20.0)
    assert p.holding is False
    assert p.ready is False


def test_idempotent_start():
    h = HoldToConfirm(10)
    h.start(0.0)
    h.start(5.0)  # non deve resettare il punto di inizio
    assert h.progress(10.0).ready is True


def test_categories():
    assert "dolore" in BYPASS_CATEGORIES
    assert len(BYPASS_CATEGORIES) == 7


def test_invalid_hold_duration():
    with pytest.raises(ValueError):
        HoldToConfirm(0)
