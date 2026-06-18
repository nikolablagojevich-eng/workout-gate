"""Test di inquadratura M0 (standalone).

Esegui dal venv 3.12:
    python scripts/camera_check.py

Apre la webcam con lo scheletro live e una checklist di visibilita' di anche,
ginocchia e caviglie. Serve a verificare che il corpo intero resti inquadrato
durante lo squat. Nessun frame viene salvato. Premi Q per uscire.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from workout_gate.config import load_config  # noqa: E402
from workout_gate.paths import config_path  # noqa: E402
from workout_gate.vision.preview import live_preview  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(live_preview(load_config(config_path())))
