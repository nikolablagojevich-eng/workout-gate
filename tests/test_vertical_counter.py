"""Test della macchina a stati 'verticale' (squat dal movimento delle spalle).

Sequenze sintetiche di posizione verticale (y cresce verso il basso): in piedi
baseline ~0.66, fondo squat ~0.80 (calo ~0.14 > min_drop 0.10). Nessuna webcam.
"""

from workout_gate.vision.squat_state import Feedback, SquatState
from workout_gate.vision.vertical_counter import VerticalRepCounter


def counter() -> VerticalRepCounter:
    return VerticalRepCounter(
        min_drop=0.10,
        hysteresis=0.02,
        min_visibility=0.6,
        standing_stability_seconds=0.4,
        min_cycle_seconds=0.8,
        max_cycle_seconds=8.0,
    )


def up(c, t, y, vis=0.99, present=True):
    return c.update(timestamp=t, body_present=present, signal_y=y, visibility=vis)


def run(c, frames):
    return [up(c, t, y, vis, present) for (t, y, vis, present) in frames]


def clean_rep(t0: float, dt: float = 0.15, baseline: float = 0.66):
    seq = []
    t = t0
    for _ in range(5):
        seq.append((t, baseline, 0.99, True))
        t += dt
    for y in (0.70, 0.76, 0.80, 0.80, 0.74, 0.70, 0.67):
        seq.append((t, y, 0.99, True))
        t += dt
    return seq, t


def test_single_clean_rep_counts_one():
    c = counter()
    seq, _ = clean_rep(0.0)
    results = run(c, seq)
    assert c.count == 1
    assert any(r.just_completed and r.feedback == Feedback.VALID for r in results)


def test_ten_clean_reps():
    c = counter()
    t = 0.0
    for _ in range(10):
        seq, t = clean_rep(t)
        run(c, seq)
    assert c.count == 10


def test_shallow_dip_not_counted():
    c = counter()
    seq = [(i * 0.15, 0.66, 0.99, True) for i in range(5)]
    t = 0.75
    for y in (0.70, 0.72, 0.70, 0.67):  # calo max 0.06 < min_drop 0.10
        seq.append((t, y, 0.99, True))
        t += 0.15
    run(c, seq)
    assert c.count == 0


def test_too_fast_rejected():
    c = counter()
    seq = [(i * 0.1, 0.66, 0.99, True) for i in range(11)]  # ~1s stabile
    seq += [(1.05, 0.80, 0.99, True), (1.10, 0.80, 0.99, True),
            (1.15, 0.72, 0.99, True), (1.20, 0.66, 0.99, True)]
    results = run(c, seq)
    assert c.count == 0
    assert any(r.feedback == Feedback.TOO_FAST for r in results)


def test_held_or_very_slow_squat_not_counted():
    # Una posizione tenuta piu' a lungo della finestra baseline viene assorbita
    # (la baseline la insegue): correttamente NON conta. Nessuno tiene il fondo 8s.
    c = counter()
    seq = [(i * 0.2, 0.66, 0.99, True) for i in range(5)]
    seq += [(1.0, 0.80, 0.99, True), (5.0, 0.80, 0.99, True),
            (9.0, 0.72, 0.99, True), (9.6, 0.66, 0.99, True)]
    run(c, seq)
    assert c.count == 0


def test_movement_before_stabilization_rejected():
    c = counter()
    seq = [(0.0, 0.66, 0.99, True), (0.1, 0.80, 0.99, True), (0.2, 0.80, 0.99, True),
           (0.6, 0.72, 0.99, True), (1.0, 0.66, 0.99, True)]
    results = run(c, seq)
    assert c.count == 0
    assert any(r.feedback == Feedback.NOT_VALID for r in results)


def test_no_double_count():
    c = counter()
    seq, t = clean_rep(0.0)
    seq += [(t + i * 0.15, 0.66, 0.99, True) for i in range(8)]
    run(c, seq)
    assert c.count == 1


def test_count_not_wiped_by_body_loss():
    # Il conteggio non deve mai azzerarsi durante la sessione (solo la rep in corso).
    c = counter()
    t = 0.0
    for _ in range(2):
        seq, t = clean_rep(t)
        run(c, seq)
    assert c.count == 2
    run(c, [(t + i * 0.15, 0.0, 0.0, False) for i in range(4)])  # corpo sparito
    t += 4 * 0.15
    assert c.count == 2  # NON azzerato
    seq, t = clean_rep(t)
    run(c, seq)
    assert c.count == 3


def test_soft_reset_keeps_count():
    c = counter()
    seq, _ = clean_rep(0.0)
    run(c, seq)
    assert c.count == 1
    c.soft_reset()
    assert c.count == 1  # il totale resta
    assert c.state == SquatState.WAITING_FOR_BODY


def test_subject_disappear_resets():
    c = counter()
    partial = [(i * 0.15, 0.66, 0.99, True) for i in range(5)]
    partial += [(0.75, 0.70, 0.99, True), (0.90, 0.78, 0.99, True)]
    partial += [(1.05, 0.0, 0.0, False)]  # corpo sparito
    results = run(c, partial)
    assert results[-1].state == SquatState.WAITING_FOR_BODY
    assert c.count == 0
    seq, _ = clean_rep(2.0)
    run(c, seq)
    assert c.count == 1


def test_low_visibility_resets():
    c = counter()
    seq = [(i * 0.15, 0.66, 0.99, True) for i in range(5)]
    seq += [(0.75, 0.72, 0.40, True)]  # visibilita' sotto soglia
    results = run(c, seq)
    assert results[-1].state == SquatState.WAITING_FOR_BODY
    assert c.count == 0


def test_transient_spike_does_not_latch_baseline():
    # Riproduce il bug visto nel log: un picco transitorio (spalle a 0.15) NON
    # deve incastrare la baseline e bloccare gli squat successivi.
    c = counter()
    seq = []
    t = 0.0
    for _ in range(6):  # in piedi a ~0.50
        seq.append((t, 0.50, 0.99, True))
        t += 0.15
    seq.append((t, 0.15, 0.99, True))  # picco transitorio di un frame
    t += 0.15
    for _ in range(3):  # squat normali 0.50 -> 0.70
        for y in [0.50] * 5 + [0.56, 0.64, 0.70, 0.70, 0.62, 0.54, 0.50]:
            seq.append((t, y, 0.99, True))
            t += 0.15
    run(c, seq)
    assert c.count >= 2


def test_baseline_autocalibrates_to_user():
    # baseline diversa (utente piu' in basso nel frame): conta comunque
    c = counter()
    t = 0.0
    seq = []
    for _ in range(5):
        seq.append((t, 0.50, 0.99, True))
        t += 0.15
    for y in (0.54, 0.60, 0.64, 0.64, 0.58, 0.54, 0.51):
        seq.append((t, y, 0.99, True))
        t += 0.15
    run(c, seq)
    assert c.count == 1
