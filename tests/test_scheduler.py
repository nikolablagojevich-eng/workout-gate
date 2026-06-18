from workout_gate.scheduler import Scheduler, SchedulerState


def make(**kw):
    calls = {"n": 0}

    def cb() -> None:
        calls["n"] += 1

    s = Scheduler(
        work_interval_seconds=10,
        idle_threshold_seconds=120,
        on_gate_due=cb,
        max_tick_gap_seconds=1000,  # niente clamp nei test deterministici
        **kw,
    )
    return s, calls


def drive(s: Scheduler, start: int, end: int, **state) -> None:
    for t in range(start, end + 1):
        s.tick(float(t), **state)


def test_gate_due_at_threshold():
    s, calls = make()
    drive(s, 0, 11)  # default: attivo
    assert calls["n"] == 1
    assert s.state == SchedulerState.GATE_OPEN


def test_idle_time_excluded():
    s, calls = make()
    drive(s, 0, 30, idle_seconds=200)  # idle > 120
    assert calls["n"] == 0


def test_locked_time_excluded():
    s, calls = make()
    drive(s, 0, 30, locked=True)
    assert calls["n"] == 0


def test_asleep_excluded():
    s, calls = make()
    drive(s, 0, 30, asleep=True)
    assert calls["n"] == 0


def test_pause_blocks_accumulation():
    s, calls = make()
    s.pause(0.0, 100)
    drive(s, 0, 30)
    assert calls["n"] == 0
    assert s.is_paused


def test_pause_expires_then_accumulates():
    s, calls = make()
    s.pause(0.0, 5)
    drive(s, 0, 25)  # pausa fino a 5, poi 10s attivi -> gate ~15
    assert calls["n"] == 1


def test_pause_until_login():
    s, calls = make()
    s.pause_until_login()
    drive(s, 0, 50)
    assert calls["n"] == 0
    s.resume()
    drive(s, 50, 65)
    assert calls["n"] == 1


def test_workout_now_opens_immediately():
    s, calls = make()
    s.workout_now()
    assert calls["n"] == 1
    assert s.gate_open


def test_completion_resets_and_starts_new_cycle():
    s, calls = make()
    drive(s, 0, 11)  # gate due
    assert s.gate_open
    s.on_workout_completed()
    assert not s.gate_open
    assert s.accumulated_seconds == 0.0
    drive(s, 12, 25)  # nuovo ciclo
    assert calls["n"] == 2


def test_emergency_bypass_uses_short_interval():
    s, calls = make(interval_after_bypass_seconds=5)
    s.workout_now()  # gate (call 1)
    s.on_emergency_bypass()
    assert not s.gate_open
    drive(s, 100, 110)  # nuova soglia: 5s
    assert calls["n"] == 2


def test_technical_error_uses_retry_interval():
    s, calls = make(retry_after_error_seconds=5)
    s.workout_now()  # call 1
    s.on_technical_error()
    assert not s.gate_open
    drive(s, 200, 210)
    assert calls["n"] == 2


def test_gate_due_fires_once():
    s, calls = make()
    drive(s, 0, 40)  # ben oltre la soglia, ma il gate resta aperto
    assert calls["n"] == 1
