from workout_gate.vision.calibration import CalibrationAccumulator


def test_derives_sensible_thresholds():
    acc = CalibrationAccumulator(min_visibility=0.6)
    for a in [172, 174, 170, 173, 171] * 10:  # in piedi
        acc.add(a, 0.9)
    for a in [95, 100, 92, 98, 96] * 10:  # fondo squat
        acc.add(a, 0.9)
    assert acc.has_enough_range()
    r = acc.result()
    assert 150 <= r.standing_knee_angle_degrees <= 178
    assert r.bottom_knee_angle_degrees < r.standing_knee_angle_degrees - 25


def test_ignores_low_visibility_samples():
    acc = CalibrationAccumulator(min_visibility=0.65)
    acc.add(170, 0.3)
    acc.add(95, 0.2)
    assert acc.samples == 0


def test_insufficient_range_not_enough():
    acc = CalibrationAccumulator()
    for a in [170] * 40:
        acc.add(a, 0.9)
    assert not acc.has_enough_range()
