"""Worker su thread separato: cattura, inferenza e disegno, fuori dal thread UI.

Emette segnali Qt verso la finestra. Il rilascio di webcam e pose detector e'
garantito in ``finally``, anche su completamento, errore o stop. In caso di
eccezione emette ``failed`` (fail-open): mai simulare il completamento.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from ..vision.draw import annotate
from .engine import WorkoutEngine

logger = logging.getLogger(__name__)


def frame_to_qimage(frame_bgr) -> QImage:
    import cv2

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return image.copy()  # stacca dal buffer numpy (che verra' liberato)


class VisionWorker(QThread):
    frameReady = Signal(object, QImage)  # (StepResult, QImage annotata)
    completed = Signal()
    failed = Signal(str)

    def __init__(
        self,
        engine_factory: Callable[[], WorkoutEngine],
        *,
        mirror: bool = True,
        fps: int = 24,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._factory = engine_factory
        self._mirror = mirror
        self._interval = 1.0 / max(1, fps)
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        engine: WorkoutEngine | None = None
        try:
            engine = self._factory()
        except Exception as exc:  # noqa: BLE001 - qualunque errore -> fail-open
            logger.exception("Inizializzazione engine fallita")
            self.failed.emit(str(exc))
            return

        try:
            while self._running:
                start = time.monotonic()
                try:
                    result = engine.step(start)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Step visione fallito")
                    self.failed.emit(str(exc))
                    return

                try:
                    annotated = annotate(
                        result.frame, result.observation, result.counter, mirror=self._mirror
                    )
                    qimg = frame_to_qimage(annotated)
                except Exception:  # noqa: BLE001 - il disegno non e' critico
                    logger.exception("Annotazione frame fallita")
                    qimg = QImage()

                # Il frame non deve sopravvivere: la UI riceve solo la QImage staccata.
                result.frame = None
                self.frameReady.emit(result, qimg)

                if result.completed:
                    self.completed.emit()
                    return

                remaining = self._interval - (time.monotonic() - start)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            if engine is not None:
                engine.close()
