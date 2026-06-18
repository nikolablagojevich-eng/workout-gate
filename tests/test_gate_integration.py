"""Integrazione del gate end-to-end con engine finto (senza webcam, senza umano).

Esercita l'intera macchina Qt: VisionWorker su thread separato, aggiornamento
finestra, flusso di completamento, chiusura e cleanup. Richiede PySide6 (presente
solo nel venv 3.12): su un interprete senza PySide6 il test viene saltato.

Usa la piattaforma Qt 'offscreen' per non aprire finestre reali.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from workout_gate.config import from_dict  # noqa: E402
from workout_gate.gate.controller import (  # noqa: E402
    OUTCOME_BYPASS,
    OUTCOME_COMPLETED,
    GateController,
)
from workout_gate.gate.engine import StepResult  # noqa: E402
from workout_gate.vision.squat_state import CounterResult, SquatState  # noqa: E402


class FakeEngine:
    """Engine che completa dopo N step, indipendente dal timing reale."""

    def __init__(self, frames_until_done: int = 20) -> None:
        self._i = 0
        self._target = frames_until_done
        self.closed = False

    def step(self, timestamp: float) -> StepResult:
        self._i += 1
        count = min(10, self._i * 10 // self._target)
        result = CounterResult(
            state=SquatState.STANDING,
            rep_count=count,
            just_completed=False,
            rejected=False,
            feedback="Test",
            confidence=0.9,
            depth_reached=False,
        )
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        return StepResult(
            observation=SimpleNamespace(present=True, landmarks=[], bbox=None),
            counter=result,
            subject_present=True,
            count=count,
            required=10,
            completed=self._i >= self._target,
            frame=frame,
        )

    def close(self) -> None:
        self.closed = True


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_gate_completes_and_releases(monkeypatch):
    app = _app()
    cfg = from_dict({"workout": {"completion_message_seconds": 0.1}})
    holder: dict = {}

    def factory():
        holder["engine"] = FakeEngine(frames_until_done=15)
        return holder["engine"]

    controller = GateController(cfg, engine_factory=factory)
    outcome: dict = {}
    controller.finished.connect(lambda o, p: (outcome.update(o=o, p=p), app.quit()))
    controller.start()
    QTimer.singleShot(8000, app.quit)  # rete di sicurezza
    app.exec()

    assert outcome.get("o") == OUTCOME_COMPLETED
    assert holder["engine"].closed is True


def test_gate_fail_open_on_engine_error():
    app = _app()
    cfg = from_dict({})

    def bad_factory():
        raise RuntimeError("MediaPipe non disponibile (simulato)")

    controller = GateController(cfg, engine_factory=bad_factory)
    outcome: dict = {}
    controller.finished.connect(lambda o, p: (outcome.update(o=o, p=p), app.quit()))
    controller.start()
    QTimer.singleShot(8000, app.quit)
    app.exec()

    # fail-open: il gate si chiude come errore tecnico, niente completamento simulato
    assert outcome.get("o") != OUTCOME_COMPLETED
    assert outcome.get("o") != OUTCOME_BYPASS
