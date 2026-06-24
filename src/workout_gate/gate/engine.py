"""Motore del workout: collega camera -> pose -> subject tracker -> counter.

Disaccoppiato da Qt e con dipendenze iniettabili (camera, pose), quindi
testabile con fake che simulano errori (fail-open) o sequenze di osservazioni
sintetiche. ``close()`` rilascia camera e pose in modo idempotente e garantito.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..config import AppConfig
from ..vision.squat_counter import SquatCounter
from ..vision.squat_state import CounterResult, FrameMetrics
from ..vision.subject_tracker import SubjectTracker

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    observation: Any
    counter: CounterResult
    subject_present: bool
    count: int
    required: int
    completed: bool
    frame: Any = None  # frame BGR transitorio, solo per il self-view. Mai salvato.


class WorkoutEngine:
    def __init__(
        self,
        *,
        camera: Any,
        pose: Any,
        counter: Any,
        tracker: SubjectTracker,
        required_reps: int,
        mode: str = "knee",
    ) -> None:
        self.camera = camera
        self.pose = pose
        self.counter = counter
        self.tracker = tracker
        self.required = required_reps
        self.mode = mode
        self._closed = False

    def step(self, timestamp: float) -> StepResult:
        """Elabora un frame. Puo' sollevare CameraError / PoseUnavailable / errori
        runtime: il chiamante li tratta come fail-open."""
        frame = self.camera.read()
        obs = self.pose.process(frame)

        candidates = [obs.bbox] if getattr(obs, "bbox", None) is not None else []
        subject = self.tracker.select(candidates)
        if subject.changed:
            # Soggetto cambiato (es. ti sei spostato molto): resetta solo la
            # ripetizione in corso, MAI il conteggio gia' raggiunto.
            self.counter.soft_reset()

        present = bool(obs.present and subject.present)
        if self.mode == "torso":
            result = self.counter.update(
                timestamp=timestamp,
                body_present=present,
                signal_y=getattr(obs, "shoulder_y", 0.0),
                visibility=getattr(obs, "shoulder_visibility", 0.0),
            )
        else:
            metrics = FrameMetrics(
                timestamp=timestamp,
                body_present=present,
                knee_angle=obs.knee_angle,
                min_visibility=obs.min_visibility,
                hip_y=getattr(obs, "hip_y", 0.0),
            )
            result = self.counter.update(metrics)
        completed = self.counter.count >= self.required
        return StepResult(
            observation=obs,
            counter=result,
            subject_present=present,
            count=self.counter.count,
            required=self.required,
            completed=completed,
            frame=frame,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.camera.release()
        finally:
            try:
                self.pose.close()
            except Exception:  # noqa: BLE001 - cleanup non deve mai propagare
                logger.exception("Errore chiudendo il pose detector (ignorato).")

    def __enter__(self) -> WorkoutEngine:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def build_counter(cfg: AppConfig) -> Any:
    """Crea il rilevatore adatto alla modalita' configurata (torso o ginocchio)."""
    v = cfg.vision
    w = cfg.workout
    if v.exercise_mode == "torso":
        from ..vision.vertical_counter import VerticalRepCounter

        # In modalita' torso la stabilita' tra le ripetizioni e' breve (default
        # del counter, 0.15s): non si penalizzano gli squat fatti in serie.
        # min_cycle volutamente basso (default del counter, 0.4s): basta che le
        # spalle scendano e risalgano, non serve uno squat profondo/lento.
        return VerticalRepCounter(
            min_drop=v.torso_min_drop,
            min_visibility=v.torso_min_visibility,
            max_cycle_seconds=w.maximum_cycle_duration_seconds,
        )
    return SquatCounter(
        standing_knee_angle=v.standing_knee_angle_degrees,
        bottom_knee_angle=v.bottom_knee_angle_degrees,
        hysteresis=v.threshold_hysteresis_degrees,
        min_visibility=v.min_landmark_visibility,
        standing_stability_seconds=v.standing_stability_seconds,
        min_cycle_seconds=w.minimum_cycle_duration_seconds,
        max_cycle_seconds=w.maximum_cycle_duration_seconds,
    )


def create_engine(cfg: AppConfig) -> WorkoutEngine:
    """Factory dell'engine reale (camera + MediaPipe). Puo' sollevare in caso di
    webcam o MediaPipe non disponibili: il chiamante applica il fail-open."""
    from ..vision.camera import Camera
    from ..vision.pose_detector import PoseDetector

    camera = Camera(index=cfg.vision.camera_index).open()
    try:
        pose = PoseDetector()
    except Exception:
        camera.release()
        raise
    return WorkoutEngine(
        camera=camera,
        pose=pose,
        counter=build_counter(cfg),
        # Tracker tollerante: con un solo utente che si sposta vicino/lontano non
        # deve scambiarlo per un soggetto nuovo a ogni movimento.
        tracker=SubjectTracker(switch_distance=0.45, lost_grace_frames=12),
        required_reps=cfg.workout.required_repetitions,
        mode=cfg.vision.exercise_mode,
    )
