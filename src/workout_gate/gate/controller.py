"""Controller del gate: collega finestra, worker visione e finestre fullscreen.

Garantisce il cleanup (stop worker + chiusura finestre + rilascio webcam) su ogni
esito: completamento, bypass o errore tecnico. Emette ``finished(outcome, payload)``
che l'app traduce in azione sullo scheduler (reset, bypass, retry).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from ..config import AppConfig
from ..ui.workout_window import WorkoutWindow
from .engine import WorkoutEngine, create_engine
from .fullscreen import GateWindows
from .vision_worker import VisionWorker

logger = logging.getLogger(__name__)

OUTCOME_COMPLETED = "completed"
OUTCOME_BYPASS = "bypass"
OUTCOME_ERROR = "error"
OUTCOME_SKIPPED = "skipped"  # gate chiuso perche' l'utente ha spento il counter (OFF)


class GateController(QObject):
    finished = Signal(str, object)  # (outcome, payload: categoria bypass o messaggio errore)

    def __init__(
        self,
        cfg: AppConfig,
        *,
        engine_factory: Callable[[], WorkoutEngine] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self._factory = engine_factory or (lambda: create_engine(cfg))
        self.window: WorkoutWindow | None = None
        self.windows: GateWindows | None = None
        self.worker: VisionWorker | None = None
        self._done = False
        self._top_timer = QTimer(self)
        self._top_timer.setInterval(2000)

    def start(self) -> None:
        self.window = WorkoutWindow(
            self.cfg.workout.required_repetitions,
            self.cfg.safety.emergency_bypass_hold_seconds,
        )
        self.window.bypassConfirmed.connect(self._on_bypass)

        self.windows = GateWindows(self.window)
        self.windows.show_all()

        self.worker = VisionWorker(
            self._factory, mirror=self.cfg.vision.mirror_preview, fps=24
        )
        self.worker.frameReady.connect(self._on_frame)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

        self._top_timer.timeout.connect(self.windows.reassert_top)
        self._top_timer.start()

    # ----- callback worker -----
    def _on_frame(self, step, qimage) -> None:
        if self.window is not None:
            self.window.update_view(step, qimage)

    def _on_completed(self) -> None:
        if self._done:
            return
        if self.window is not None:
            self.window.show_completion()
        delay = int(self.cfg.workout.completion_message_seconds * 1000)
        QTimer.singleShot(delay, lambda: self._finish(OUTCOME_COMPLETED, None))

    def _on_failed(self, message: str) -> None:
        if self._done:
            return
        logger.warning("Fail-open del gate: %s", message)
        if self.window is not None:
            self.window.feedback.setText("Problema tecnico con la webcam: riprendo piu' tardi.")
        QTimer.singleShot(1200, lambda: self._finish(OUTCOME_ERROR, message))

    def _on_bypass(self, category: str) -> None:
        self._finish(OUTCOME_BYPASS, category)

    def cancel(self) -> None:
        """Chiude il gate senza debito (es. l'utente ha premuto OFF: riunione)."""
        self._finish(OUTCOME_SKIPPED, None)

    # ----- chiusura -----
    def _finish(self, outcome: str, payload) -> None:
        if self._done:
            return
        self._done = True
        self._top_timer.stop()
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(4000)
        if self.window is not None:
            self.window._completed = True  # consente la chiusura
        if self.windows is not None:
            self.windows.close_all()
        logger.info("Gate chiuso, esito=%s", outcome)
        self.finished.emit(outcome, payload)
