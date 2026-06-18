"""Preview webcam e calibrazione interattive via OpenCV (standalone, no Qt).

``live_preview`` e' anche il test di inquadratura (M0) per Nik: mostra lo scheletro
live e una checklist di visibilita' di anche/ginocchia/caviglie, per verificare che
il corpo intero resti inquadrato durante lo squat. Nessun frame viene salvato.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..config import AppConfig
from .pose_detector import L_ANKLE, L_HIP, L_KNEE, R_ANKLE, R_HIP, R_KNEE

logger = logging.getLogger(__name__)


class _Info:
    """Oggetto minimo richiesto da draw.annotate (confidence + phase_label)."""

    def __init__(self, confidence: float, phase_label: str) -> None:
        self.confidence = confidence
        self.phase_label = phase_label


def _leg_visibility(observation) -> dict[str, bool]:
    lms = getattr(observation, "landmarks", None) or []

    def vis(i: int) -> bool:
        return i < len(lms) and lms[i][2] >= 0.5

    return {
        "anche": vis(L_HIP) and vis(R_HIP),
        "ginocchia": vis(L_KNEE) and vis(R_KNEE),
        "caviglie": vis(L_ANKLE) and vis(R_ANKLE),
    }


def live_preview(cfg: AppConfig, *, duration: float | None = None) -> int:
    import cv2

    from .camera import Camera
    from .draw import annotate
    from .pose_detector import PoseDetector

    title = "Workout Gate - Test webcam (Q per uscire)"
    print("Test webcam: posizionati e fai 2-3 squat.")
    print("Servono anche, ginocchia e caviglie visibili anche in fondo allo squat.")
    print("Premi Q nella finestra per uscire. Nessun frame viene salvato.")

    start = time.monotonic()
    with Camera(index=cfg.vision.camera_index) as cam, PoseDetector() as pose:
        while True:
            frame = cam.read()
            obs = pose.process(frame)
            info = _Info(obs.min_visibility, "Corpo rilevato" if obs.present else "Nessun corpo")
            img = annotate(frame, obs, info, mirror=cfg.vision.mirror_preview)

            flags = _leg_visibility(obs)
            y = 60
            for name, ok in flags.items():
                color = (80, 220, 120) if ok else (80, 80, 230)
                cv2.putText(
                    img, f"{name}: {'OK' if ok else 'NON visibili'}", (12, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA,
                )
                y += 28
            if obs.present:
                cv2.putText(
                    img, f"ginocchio: {obs.knee_angle:.0f} gradi", (12, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
                )

            cv2.imshow(title, img)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
            if duration is not None and time.monotonic() - start > duration:
                break
        cv2.destroyAllWindows()
    return 0


def calibrate_interactive(cfg: AppConfig, config_file: Path) -> int:
    import cv2

    from .calibration import CalibrationAccumulator
    from .camera import Camera
    from .draw import annotate
    from .pose_detector import PoseDetector

    collect_seconds = 8.0
    title = "Workout Gate - Calibrazione"
    print("Calibrazione: premi SPAZIO, poi resta in piedi e fai 2-3 squat completi.")
    print("Premi Q per uscire. Si salvano solo soglie numeriche, nessuna immagine.")

    acc = CalibrationAccumulator(min_visibility=cfg.vision.min_landmark_visibility)
    collecting = False
    collect_start = 0.0
    saved = False

    with Camera(index=cfg.vision.camera_index) as cam, PoseDetector() as pose:
        while True:
            frame = cam.read()
            obs = pose.process(frame)
            info = _Info(obs.min_visibility, "Calibrazione" if collecting else "Pronto")
            img = annotate(frame, obs, info, mirror=cfg.vision.mirror_preview)

            if collecting:
                acc.add(obs.knee_angle, obs.min_visibility, present=obs.present)
                remaining = collect_seconds - (time.monotonic() - collect_start)
                cv2.putText(
                    img, f"Calibrazione... {max(0, remaining):.0f}s  ({acc.samples} campioni)",
                    (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 220, 255), 2, cv2.LINE_AA,
                )
                if remaining <= 0:
                    collecting = False
                    if acc.has_enough_range():
                        result = acc.result()
                        _save_thresholds(config_file, result)
                        saved = True
                        print(
                            f"Calibrazione salvata: standing={result.standing_knee_angle_degrees} "
                            f"bottom={result.bottom_knee_angle_degrees} ({result.samples} campioni)"
                        )
                        break
                    print("Movimento insufficiente: stai in piedi e fai squat completi. Riprova.")
            else:
                cv2.putText(
                    img, "SPAZIO: avvia calibrazione 8s   Q: esci", (12, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 2, cv2.LINE_AA,
                )

            cv2.imshow(title, img)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" ") and not collecting:
                acc = CalibrationAccumulator(min_visibility=cfg.vision.min_landmark_visibility)
                collecting = True
                collect_start = time.monotonic()
        cv2.destroyAllWindows()
    return 0 if saved else 1


def _save_thresholds(config_file: Path, result) -> None:
    import yaml

    data: dict = {}
    if config_file.exists():
        try:
            data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
    vision = data.setdefault("vision", {})
    vision["standing_knee_angle_degrees"] = result.standing_knee_angle_degrees
    vision["bottom_knee_angle_degrees"] = result.bottom_knee_angle_degrees
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
