import pytest

from workout_gate.active_time import ActiveTimeTracker


def test_accumulates_active_deltas():
    t = ActiveTimeTracker(30)
    assert t.tick(0.0, active=True) == 0.0  # primo tick: init
    assert t.tick(1.0, active=True) == 1.0
    assert t.tick(2.0, active=True) == 1.0
    assert t.accumulated == 2.0


def test_excludes_inactive_time():
    t = ActiveTimeTracker(30)
    t.tick(0.0, active=True)
    t.tick(1.0, active=True)  # +1
    t.tick(2.0, active=False)  # escluso (idle/lock/pause)
    t.tick(3.0, active=False)
    t.tick(4.0, active=True)  # +1
    assert t.accumulated == 2.0


def test_clamps_large_gap_as_sleep():
    t = ActiveTimeTracker(30, max_tick_gap_seconds=5)
    t.tick(0.0, active=True)
    t.tick(1.0, active=True)  # +1
    t.tick(100.0, active=True)  # gap 99s > 5 -> NON conteggiato (sospensione)
    assert t.accumulated == 1.0


def test_reached_threshold():
    t = ActiveTimeTracker(2)
    t.tick(0.0, active=True)
    t.tick(1.0, active=True)
    assert not t.reached()
    t.tick(2.0, active=True)
    assert t.reached()


def test_remaining():
    t = ActiveTimeTracker(10)
    t.tick(0.0, active=True)
    t.tick(3.0, active=True)
    assert t.remaining() == 7.0


def test_reset_zeroes_accumulated_not_clock():
    t = ActiveTimeTracker(30)
    t.tick(0.0, active=True)
    t.tick(5.0, active=True)
    t.reset()
    assert t.accumulated == 0.0
    # il clock continua: prossimo tick misura dal precedente
    assert t.tick(6.0, active=True) == 1.0


def test_load_restores_accumulated_after_restart():
    t = ActiveTimeTracker(30, initial_accumulated=22.0 * 60)
    assert t.accumulated == 22.0 * 60
    t.load(100.0)
    assert t.accumulated == 100.0


def test_detach_clock_drops_gap():
    t = ActiveTimeTracker(30)
    t.tick(0.0, active=True)
    t.tick(1.0, active=True)  # +1
    t.detach_clock()  # es. resume da sleep
    assert t.tick(500.0, active=True) == 0.0  # re-init, nessun salto conteggiato
    assert t.tick(501.0, active=True) == 1.0
    assert t.accumulated == 2.0


def test_rejects_invalid_interval():
    with pytest.raises(ValueError):
        ActiveTimeTracker(0)
