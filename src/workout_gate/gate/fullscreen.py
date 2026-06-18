"""Finestre fullscreen multi-monitor, topmost ma 'soft' (niente guerra di focus).

La finestra principale (workout) sta sullo schermo primario; gli altri schermi
ricevono un blocco oscurato. Tutte sono frameless e WindowStaysOnTop. Non si
combatte per il focus: e' un invito a muoversi, non un kiosk inviolabile. Se uno
schermo non e' copribile, si applica il fail-open a monte (errore tecnico).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_GATE_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
)


class BlockerWindow(QWidget):
    """Schermo secondario oscurato durante il workout."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(_GATE_FLAGS)
        self.setStyleSheet("background-color: #0D1B2A;")
        layout = QVBoxLayout(self)
        label = QLabel("Workout Gate in corso\nCompleta gli squat sullo schermo principale")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color:#9DB2C8; font-size:22px;")
        layout.addWidget(label)


class GateWindows:
    def __init__(self, primary: QWidget) -> None:
        self.primary = primary
        self._blockers: list[BlockerWindow] = []

    def show_all(self) -> None:
        screens = QGuiApplication.screens()
        primary_screen = QGuiApplication.primaryScreen()

        self.primary.setWindowFlags(_GATE_FLAGS)
        if primary_screen is not None:
            self.primary.setGeometry(primary_screen.geometry())
        self.primary.showFullScreen()
        self.primary.raise_()
        self.primary.activateWindow()

        for screen in screens:
            if screen is primary_screen:
                continue
            blocker = BlockerWindow()
            blocker.setGeometry(screen.geometry())
            blocker.showFullScreen()
            blocker.raise_()
            self._blockers.append(blocker)

    def reassert_top(self) -> None:
        """Richiamo gentile in cima (no loop aggressivo)."""
        self.primary.raise_()
        for b in self._blockers:
            b.raise_()

    def close_all(self) -> None:
        for b in self._blockers:
            try:
                b.close()
            except Exception:  # noqa: BLE001
                pass
        self._blockers.clear()
        try:
            self.primary.close()
        except Exception:  # noqa: BLE001
            pass
