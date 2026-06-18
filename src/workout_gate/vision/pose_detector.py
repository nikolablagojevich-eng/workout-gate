"""Pose estimation con MediaPipe Tasks PoseLandmarker (import lazy).

La build di MediaPipe installata (0.10.x) espone solo l'API Tasks, non la legacy
``solutions``. Si usa quindi ``PoseLandmarker`` in running mode VIDEO, con il
modello ``pose_landmarker_lite.task`` bundlato nel pacchetto: nessun download a
runtime, nessuna chiamata di rete (coerente con la privacy).

Da ogni frame estrae le metriche numeriche per la macchina a stati: angolo del
ginocchio (lato piu' visibile o media dei due), visibilita' minima dei landmark
usati, posizione verticale dell'anca, bounding box. Ritorna anche i landmark
normalizzati del frame corrente SOLO per il disegno a schermo: mai salvati.

Limite onesto: v1 lavora su un singolo soggetto (``num_poses=1``); MediaPipe
seleziona la posa piu' prominente. Il subject tracker resta nel pipeline per la
continuita' e per un futuro passaggio a multi-posa.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import angle_at
from .squat_state import FrameMetrics
from .subject_tracker import Candidate

logger = logging.getLogger(__name__)

# Indici landmark MediaPipe Pose (topologia a 33 punti, invariata in Tasks).
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

MODEL_PATH = Path(__file__).resolve().parent / "models" / "pose_landmarker_lite.task"


class PoseUnavailable(RuntimeError):
    """MediaPipe non disponibile, modello mancante o non inizializzabile."""


@dataclass
class PoseObservation:
    present: bool
    knee_angle: float = 180.0
    min_visibility: float = 0.0
    hip_y: float = 0.0
    # Posizione verticale (e visibilita') delle spalle: segnale della modalita' torso.
    shoulder_y: float = 0.0
    shoulder_visibility: float = 0.0
    # Landmark normalizzati (x, y, visibility) del frame corrente, solo per disegno.
    landmarks: list[tuple[float, float, float]] = field(default_factory=list)
    bbox: Candidate | None = None

    def to_metrics(self, timestamp: float) -> FrameMetrics:
        return FrameMetrics(
            timestamp=timestamp,
            body_present=self.present,
            knee_angle=self.knee_angle,
            min_visibility=self.min_visibility,
            hip_y=self.hip_y,
        )


class PoseDetector:
    def __init__(
        self,
        *,
        model_path: str | Path | None = None,
        num_poses: int = 1,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except Exception as exc:  # noqa: BLE001
            raise PoseUnavailable(f"MediaPipe non importabile: {exc}") from exc

        path = Path(model_path) if model_path else MODEL_PATH
        if not path.exists():
            raise PoseUnavailable(f"Modello PoseLandmarker non trovato: {path}")

        try:
            self._mp = mp
            options = vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=num_poses,
                min_pose_detection_confidence=min_detection_confidence,
                min_pose_presence_confidence=min_presence_confidence,
                min_tracking_confidence=min_tracking_confidence,
                output_segmentation_masks=False,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
        except Exception as exc:  # noqa: BLE001
            raise PoseUnavailable(f"Inizializzazione PoseLandmarker fallita: {exc}") from exc

        self._ts_ms = 0

    def process(self, frame_bgr) -> PoseObservation:
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        # detect_for_video richiede timestamp in ms strettamente crescenti.
        self._ts_ms += 33
        result = self._landmarker.detect_for_video(mp_image, self._ts_ms)

        poses = result.pose_landmarks
        if not poses:
            return PoseObservation(present=False)

        lm = poses[0]

        def pt(i: int) -> tuple[float, float]:
            return (lm[i].x, lm[i].y)

        def vis(i: int) -> float:
            return float(getattr(lm[i], "visibility", 1.0) or 0.0)

        left_vis = min(vis(L_HIP), vis(L_KNEE), vis(L_ANKLE))
        right_vis = min(vis(R_HIP), vis(R_KNEE), vis(R_ANKLE))
        left_angle = angle_at(pt(L_HIP), pt(L_KNEE), pt(L_ANKLE))
        right_angle = angle_at(pt(R_HIP), pt(R_KNEE), pt(R_ANKLE))

        good = 0.5
        if left_vis >= good and right_vis >= good:
            knee_angle = (left_angle + right_angle) / 2.0
            min_visibility = min(left_vis, right_vis)
        elif left_vis >= right_vis:
            knee_angle, min_visibility = left_angle, left_vis
        else:
            knee_angle, min_visibility = right_angle, right_vis

        hip_y = (lm[L_HIP].y + lm[R_HIP].y) / 2.0
        shoulder_y = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2.0
        shoulder_visibility = (vis(L_SHOULDER) + vis(R_SHOULDER)) / 2.0
        landmarks = [(float(p.x), float(p.y), vis(i)) for i, p in enumerate(lm)]
        bbox = self._bbox(landmarks)

        return PoseObservation(
            present=True,
            knee_angle=knee_angle,
            min_visibility=min_visibility,
            hip_y=hip_y,
            shoulder_y=shoulder_y,
            shoulder_visibility=shoulder_visibility,
            landmarks=landmarks,
            bbox=bbox,
        )

    @staticmethod
    def _bbox(
        landmarks: list[tuple[float, float, float]], vis_threshold: float = 0.5
    ) -> Candidate | None:
        xs = [x for x, _, v in landmarks if v >= vis_threshold]
        ys = [y for _, y, v in landmarks if v >= vis_threshold]
        if not xs or not ys:
            return None
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return Candidate(cx=(x0 + x1) / 2, cy=(y0 + y1) / 2, width=x1 - x0, height=y1 - y0)

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:  # noqa: BLE001 - cleanup idempotente
            pass

    def __enter__(self) -> PoseDetector:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
