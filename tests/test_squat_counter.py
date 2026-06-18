"""Test della macchina a stati dello squat su sequenze di metriche sintetiche.

Nessun video, nessuna webcam: si alimenta il counter con FrameMetrics numeriche
che rappresentano squat puliti, mezzi squat, rimbalzi, movimenti troppo
rapidi/lenti, sparizione del soggetto. E' la verifica formale del cuore del
sistema, eseguibile in CI.
"""

from workout_gate.vision.squat_counter import SquatCounter
from workout_gate.vision.squat_state import CounterResult, Feedback, FrameMetrics, SquatState


def counter() -> SquatCounter:
    return SquatCounter(
        standing_knee_angle=160,
        bottom_knee_angle=100,
        hysteresis=8,
        min_visibility=0.65,
        standing_stability_seconds=0.4,
        min_cycle_seconds=0.8,
        max_cycle_seconds=8.0,
    )


def fm(angle: float, t: float, vis: float = 0.99, present: bool = True) -> FrameMetrics:
    return FrameMetrics(timestamp=t, body_present=present, knee_angle=angle, min_visibility=vis)


def run(c: SquatCounter, frames: list[FrameMetrics]) -> list[CounterResult]:
    return [c.update(f) for f in frames]


def clean_rep(t0: float, dt: float = 0.12, stand_frames: int = 5):
    """Genera i frame di uno squat pulito a partire da t0. Ritorna (frames, t_next)."""
    seq: list[FrameMetrics] = []
    t = t0
    for _ in range(stand_frames):
        seq.append(fm(175, t))
        t += dt
    for a in (148, 128, 108, 94, 94, 108, 128, 148, 172):
        seq.append(fm(a, t))
        t += dt
    return seq, t


def test_single_clean_squat_counts_one():
    c = counter()
    seq, _ = clean_rep(0.0)
    results = run(c, seq)
    assert c.count == 1
    assert any(r.just_completed for r in results)


def test_completion_feedback_is_valid():
    c = counter()
    seq, _ = clean_rep(0.0)
    results = run(c, seq)
    assert any(r.just_completed and r.feedback == Feedback.VALID for r in results)


def test_ten_clean_squats_count_ten():
    c = counter()
    t = 0.0
    for _ in range(10):
        seq, t = clean_rep(t)
        run(c, seq)
    assert c.count == 10


def test_half_squat_not_counted():
    c = counter()
    seq = [fm(175, i * 0.12) for i in range(5)]
    t = 0.6
    for a in (148, 135, 130, 135, 148, 172):  # scende solo a 130, sopra il fondo
        seq.append(fm(a, t))
        t += 0.12
    run(c, seq)
    assert c.count == 0


def test_threshold_oscillation_not_counted():
    c = counter()
    seq = [fm(175, i * 0.1) for i in range(6)]
    t = 0.6
    for a in (150, 154, 151, 155, 150, 156, 175):
        seq.append(fm(a, t))
        t += 0.1
    run(c, seq)
    assert c.count == 0


def test_too_fast_rejected():
    c = counter()
    seq = [fm(175, i * 0.1) for i in range(12)]  # ~1.1s in piedi stabile
    seq += [fm(148, 1.15), fm(94, 1.20), fm(172, 1.25), fm(172, 1.30)]  # ciclo 0.15s
    results = run(c, seq)
    assert c.count == 0
    assert any(r.feedback == Feedback.TOO_FAST for r in results)


def test_too_slow_rejected():
    c = counter()
    seq = [fm(175, i * 0.2) for i in range(5)]  # stabile
    seq += [fm(148, 1.0), fm(94, 4.0), fm(108, 7.0), fm(172, 10.5), fm(172, 11.0)]  # 9.5s
    results = run(c, seq)
    assert c.count == 0
    assert any(r.feedback == Feedback.TOO_SLOW for r in results)


def test_movement_before_stabilization_rejected():
    c = counter()
    # discesa immediata, durata valida ma start non stabilizzato
    seq = [fm(175, 0.0), fm(148, 0.1), fm(94, 0.5), fm(108, 0.9), fm(172, 1.0), fm(172, 1.1)]
    results = run(c, seq)
    assert c.count == 0
    assert any(r.feedback == Feedback.NOT_VALID for r in results)


def test_no_double_count_on_extra_standing():
    c = counter()
    seq, t = clean_rep(0.0)
    seq += [fm(175, t + i * 0.12) for i in range(10)]
    run(c, seq)
    assert c.count == 1


def test_subject_disappear_cancels_in_progress_rep():
    c = counter()
    partial = [fm(175, i * 0.12) for i in range(5)]
    partial += [fm(148, 0.6), fm(128, 0.72), fm(108, 0.84)]
    partial += [fm(0, 0.96, present=False)]  # soggetto sparito a meta' discesa
    results = run(c, partial)
    assert results[-1].state == SquatState.WAITING_FOR_BODY
    assert c.count == 0
    seq, _ = clean_rep(2.0)
    run(c, seq)
    assert c.count == 1


def test_low_visibility_resets():
    c = counter()
    seq = [fm(175, i * 0.12) for i in range(5)]
    seq += [fm(148, 0.6), fm(128, 0.72), fm(110, 0.84, vis=0.40)]
    results = run(c, seq)
    assert results[-1].state == SquatState.WAITING_FOR_BODY
    assert c.count == 0


def test_waiting_to_standing_transition():
    c = counter()
    res = c.update(fm(175, 0.0))
    assert res.state == SquatState.STANDING


def test_bounce_at_bottom_is_single_rep():
    c = counter()
    seq = [fm(175, i * 0.12) for i in range(5)]
    t = 0.6
    for a in (148, 110, 94, 105, 94, 105, 94, 110, 130, 150, 172):
        seq.append(fm(a, t))
        t += 0.12
    run(c, seq)
    assert c.count == 1
