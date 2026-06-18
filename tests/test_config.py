import pytest

from workout_gate.config import ConfigError, from_dict, with_dev_interval


def test_defaults():
    c = from_dict({})
    assert c.timer.work_interval_minutes == 30
    assert c.workout.required_repetitions == 10
    assert c.timer.work_interval_seconds == 1800


def test_privacy_is_forced_off():
    c = from_dict({"privacy": {"save_video": True, "telemetry": True, "network_access": True}})
    assert c.privacy.save_video is False
    assert c.privacy.telemetry is False
    assert c.privacy.network_access is False


def test_invalid_knee_angles():
    with pytest.raises(ConfigError):
        from_dict({"vision": {"standing_knee_angle_degrees": 90, "bottom_knee_angle_degrees": 100}})


def test_hysteresis_too_wide():
    with pytest.raises(ConfigError):
        from_dict({"vision": {"threshold_hysteresis_degrees": 40}})


def test_cycle_bounds_must_be_ordered():
    with pytest.raises(ConfigError):
        from_dict(
            {"workout": {"minimum_cycle_duration_seconds": 5, "maximum_cycle_duration_seconds": 2}}
        )


def test_visibility_range():
    with pytest.raises(ConfigError):
        from_dict({"vision": {"min_landmark_visibility": 1.5}})


def test_unknown_exercise_rejected():
    with pytest.raises(ConfigError):
        from_dict({"workout": {"exercise": "burpee"}})


def test_unknown_keys_ignored():
    c = from_dict({"timer": {"work_interval_minutes": 10, "bogus_key": 1}})
    assert c.timer.work_interval_minutes == 10


def test_dev_interval_override():
    c = with_dev_interval(from_dict({}), 30)
    assert c.effective_work_interval_seconds == 30
    assert c.dev_work_interval_seconds == 30


def test_dev_interval_must_be_positive():
    with pytest.raises(ConfigError):
        with_dev_interval(from_dict({}), -5)
