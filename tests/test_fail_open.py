"""Fail-open e cleanup garantito a livello di engine, con camera/pose fake."""

import pytest

from workout_gate.gate.engine import WorkoutEngine
from workout_gate.vision.camera import CameraError
from workout_gate.vision.pose_detector import PoseObservation
from workout_gate.vision.squat_counter import SquatCounter
from workout_gate.vision.subject_tracker import Candidate, SubjectTracker


class FakeCamera:
    def __init__(self, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.reads = 0
        self.released = False

    def read(self):
        if self.fail_after is not None and self.reads >= self.fail_after:
            raise CameraError("webcam scollegata (simulata)")
        self.reads += 1
        return object()  # frame sentinella (i fake pose non lo usano)

    def release(self) -> None:
        self.released = True


class FakePose:
    def __init__(self, observations) -> None:
        self._obs = list(observations)
        self._i = 0
        self.closed = False

    def process(self, frame) -> PoseObservation:
        o = self._obs[min(self._i, len(self._obs) - 1)]
        self._i += 1
        return o

    def close(self) -> None:
        self.closed = True


def obs(angle: float, present: bool = True, vis: float = 0.99) -> PoseObservation:
    return PoseObservation(
        present=present,
        knee_angle=angle,
        min_visibility=vis,
        hip_y=0.5,
        landmarks=[],
        bbox=Candidate(0.5, 0.5, 0.3, 0.7),
    )


def squat_stream(reps: int = 10, dt: float = 0.12):
    seq = []
    t = 0.0
    for _ in range(reps):
        for a in [175] * 5 + [148, 128, 108, 94, 94, 108, 128, 148, 172]:
            seq.append((t, a))
            t += dt
    return seq


def make_engine(observations, *, required=10, fail_after=None):
    cam = FakeCamera(fail_after=fail_after)
    pose = FakePose(observations)
    engine = WorkoutEngine(
        camera=cam,
        pose=pose,
        counter=SquatCounter(),
        tracker=SubjectTracker(),
        required_reps=required,
    )
    return engine, cam, pose


def test_engine_completes_after_ten_squats():
    stream = squat_stream(10)
    engine, cam, pose = make_engine([obs(a) for _, a in stream], required=10)
    completed = False
    try:
        for t, _ in stream:
            res = engine.step(t)
            completed = completed or res.completed
    finally:
        engine.close()
    assert completed
    assert engine.counter.count == 10
    assert cam.released and pose.closed


def test_camera_failure_propagates_and_cleans_up():
    engine, cam, pose = make_engine([obs(175)], required=10, fail_after=0)
    with pytest.raises(CameraError):
        engine.step(0.0)
    engine.close()
    assert cam.released is True
    assert pose.closed is True


def test_close_is_idempotent():
    engine, cam, pose = make_engine([obs(175)])
    engine.close()
    engine.close()  # secondo close non deve esplodere
    assert cam.released and pose.closed


def test_nine_squats_do_not_complete():
    stream = squat_stream(9)
    engine, _, _ = make_engine([obs(a) for _, a in stream], required=10)
    try:
        results = [engine.step(t) for t, _ in stream]
    finally:
        engine.close()
    assert engine.counter.count == 9
    assert not any(r.completed for r in results)
