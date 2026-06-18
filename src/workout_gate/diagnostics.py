"""Diagnostica ambiente (``workout-gate doctor``)."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass

from .config import load_config
from .paths import config_path, data_dir
from .vision.pose_detector import MODEL_PATH


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _check_camera() -> tuple[bool, str]:
    try:
        from .vision.camera import Camera, CameraError

        cam = Camera()
        try:
            cam.open()
            try:
                cam.read()
                return True, "aperta e leggibile"
            except CameraError as exc:
                return True, f"aperta ma frame non leggibile: {exc}"
        finally:
            cam.release()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run_checks(*, include_camera: bool = True) -> list[Check]:
    checks: list[Check] = []

    py_ok = sys.version_info[:2] in {(3, 11), (3, 12), (3, 13)}
    checks.append(Check("Python 3.11-3.13", py_ok, sys.version.split()[0]))

    for mod, label in [
        ("cv2", "OpenCV"),
        ("mediapipe", "MediaPipe"),
        ("PySide6", "PySide6"),
        ("numpy", "NumPy"),
        ("yaml", "PyYAML"),
    ]:
        ok = _has(mod)
        checks.append(Check(label, ok, "installato" if ok else "MANCANTE"))

    checks.append(
        Check("Modello PoseLandmarker", MODEL_PATH.exists(), str(MODEL_PATH))
    )

    try:
        d = data_dir()
        probe = d / ".write_test"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        checks.append(Check("Data dir scrivibile", True, str(d)))
    except OSError as exc:
        checks.append(Check("Data dir scrivibile", False, str(exc)))

    try:
        load_config(config_path())
        checks.append(Check("Config valida", True, str(config_path())))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("Config valida", False, str(exc)))

    if include_camera:
        ok, detail = _check_camera()
        checks.append(Check("Webcam apribile", ok, detail))

    return checks


def doctor(*, include_camera: bool = True) -> int:
    checks = run_checks(include_camera=include_camera)
    print("Workout Gate - diagnostica\n")
    all_ok = True
    for c in checks:
        mark = "OK" if c.ok else "!!"
        all_ok = all_ok and c.ok
        print(f"  [{mark}] {c.name}: {c.detail}")
    print()
    print("Tutto a posto." if all_ok else "Alcuni controlli sono falliti (vedi sopra).")
    return 0 if all_ok else 1
