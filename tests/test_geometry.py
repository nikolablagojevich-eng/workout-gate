from workout_gate.vision.geometry import angle_at, clamp, midpoint


def test_straight_leg_is_180():
    # hip, knee, ankle in linea verticale -> gamba estesa
    assert angle_at((0, 0), (0, 1), (0, 2)) == 180.0


def test_right_angle():
    assert abs(angle_at((0, 0), (0, 1), (1, 1)) - 90.0) < 1e-6


def test_acute_angle_squat_bottom():
    # ginocchio molto piegato -> angolo piccolo
    a = angle_at((0, 0), (0, 1), (0.1, 0.2))
    assert a < 90.0


def test_degenerate_returns_180():
    # landmark coincidenti: non deve esplodere
    assert angle_at((1, 1), (1, 1), (2, 2)) == 180.0


def test_midpoint_and_clamp():
    assert midpoint((0, 0), (2, 4)) == (1.0, 2.0)
    assert clamp(5, 0, 1) == 1
    assert clamp(-5, 0, 1) == 0
    assert clamp(0.5, 0, 1) == 0.5
