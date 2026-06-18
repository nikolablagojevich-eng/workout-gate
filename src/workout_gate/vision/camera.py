"""Acquisizione webcam via OpenCV, come context manager con rilascio garantito.

Privacy: i frame restano in memoria solo per l'elaborazione. Nessuna scrittura
su disco, mai. OpenCV viene importato in modo lazy (non e' richiesto per i test
del core).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CameraError(RuntimeError):
    """Webcam assente, occupata, disconnessa o frame non leggibile."""


class Camera:
    def __init__(self, index: int = 0, width: int = 1280, height: int = 720) -> None:
        self.index = index
        self.width = width
        self.height = height
        self._cap: Any | None = None
        self._cv2: Any | None = None

    def open(self) -> Camera:
        import cv2

        self._cv2 = cv2
        # CAP_DSHOW: backend piu' rapido e affidabile su Windows.
        backend = getattr(cv2, "CAP_DSHOW", 0)
        cap = cv2.VideoCapture(self.index, backend)
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            raise CameraError(f"Impossibile aprire la webcam (index {self.index}).")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap = cap
        logger.info("Webcam %s aperta (%sx%s).", self.index, self.width, self.height)
        return self

    def read(self):
        if self._cap is None:
            raise CameraError("Webcam non aperta.")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError("Lettura frame fallita (webcam disconnessa?).")
        return frame

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None
                logger.info("Webcam rilasciata.")

    def __enter__(self) -> Camera:
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
