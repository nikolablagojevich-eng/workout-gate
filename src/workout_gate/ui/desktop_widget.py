"""Widget desktop con interruttore retro ON/OFF.

Piccola finestra senza bordi, sempre in primo piano, trascinabile, con due
pulsanti vecchio stile. ON tiene attivo il counter; OFF lo spegne (pausa a tempo
indeterminato) per quando non ci si puo' permettere il blocco schermo (riunioni,
presentazioni). Emette i segnali ``turnedOn``/``turnedOff``: la logica vive
nell'app/scheduler, qui solo presentazione e stato.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Costanti Win32 per mandare la finestra in fondo allo z-order, senza attivarla.
_GWL_EXSTYLE = -20
_WS_EX_NOACTIVATE = 0x08000000
_HWND_BOTTOM = 1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_BOTTOM = _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE


def _user32():
    """user32 con tipi configurati (su 64-bit gli handle non vanno troncati)."""
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32  # type: ignore[attr-defined]
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowLongW.restype = wintypes.LONG
    u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    u.SetWindowLongW.restype = wintypes.LONG
    u.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    u.SetWindowPos.restype = wintypes.BOOL
    u.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    u.SetParent.restype = wintypes.HWND
    return u


def _as_long(value: int) -> int:
    """Riporta un intero a LONG signed a 32 bit (evita overflow ctypes)."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value

_PANEL = """
QWidget#WidgetRoot {
    background-color: #161616;
    border-top: 2px solid #3a3a3a;
    border-left: 2px solid #3a3a3a;
    border-right: 2px solid #050505;
    border-bottom: 2px solid #050505;
    border-radius: 6px;
}
QLabel#Title {
    color: #8a8f98; font-family: Consolas, monospace;
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
}
QLabel#Status { color: #C9A24A; font-family: Consolas, monospace; font-size: 12px; }
QPushButton {
    font-family: Consolas, monospace; font-weight: 800; font-size: 16px;
    color: #2a2a2a; border-radius: 5px; padding: 10px 0; min-width: 78px;
    border-top: 2px solid #6a6a6a; border-left: 2px solid #6a6a6a;
    border-right: 2px solid #0a0a0a; border-bottom: 2px solid #0a0a0a;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5a5a5a, stop:1 #3a3a3a);
}
QPushButton#On[lit="true"] {
    color: #06250e;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6df08a, stop:1 #28a045);
    border-top: 2px solid #9dffb6; border-left: 2px solid #9dffb6;
}
QPushButton#Off[lit="true"] {
    color: #2a0606;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff7a7a, stop:1 #c0392b);
    border-top: 2px solid #ffb0b0; border-left: 2px solid #ffb0b0;
}
"""


class DesktopWidget(QWidget):
    turnedOn = Signal()
    turnedOff = Signal()

    def __init__(self) -> None:
        super().__init__()
        # Niente "sempre in primo piano": il widget vive sullo sfondo del desktop
        # (vedi pin_to_desktop), cosi' non galleggia sopra le finestre ne' appare
        # nelle condivisioni schermo.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setObjectName("WidgetRoot")
        self.setStyleSheet(_PANEL)
        self.setFixedSize(196, 104)
        self._drag_offset: QPoint | None = None
        self._front_mode = False  # True quando portato in primo piano dall'icona
        self._bottom_timer = QTimer(self)
        self._bottom_timer.setInterval(4000)
        self._bottom_timer.timeout.connect(self._reassert_bottom)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(6)

        self._title = QLabel("WORKOUT GATE")
        self._title.setObjectName("Title")
        root.addWidget(self._title)

        self._status = QLabel("attivo")
        self._status.setObjectName("Status")
        root.addWidget(self._status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._on = QPushButton("ON")
        self._on.setObjectName("On")
        self._on.clicked.connect(self._clicked_on)
        self._off = QPushButton("OFF")
        self._off.setObjectName("Off")
        self._off.clicked.connect(self._clicked_off)
        buttons.addWidget(self._on)
        buttons.addWidget(self._off)
        root.addLayout(buttons)

        self.set_state(enabled=True, status="attivo")

    def set_state(self, *, enabled: bool, status: str) -> None:
        self._status.setText(status)
        self._set_lit(self._on, enabled)
        self._set_lit(self._off, not enabled)

    @staticmethod
    def _set_lit(button: QPushButton, lit: bool) -> None:
        button.setProperty("lit", "true" if lit else "false")
        # Forza il ricalcolo dello stile dopo il cambio di property.
        button.style().unpolish(button)
        button.style().polish(button)

    def _clicked_on(self) -> None:
        self.turnedOn.emit()
        self._return_to_background_if_summoned()

    def _clicked_off(self) -> None:
        self.turnedOff.emit()
        self._return_to_background_if_summoned()

    def _return_to_background_if_summoned(self) -> None:
        # Se era stato richiamato in primo piano dall'icona, dopo il click torna
        # sullo sfondo da solo (cosi' non resta davanti, es. durante una riunione).
        if self._front_mode:
            QTimer.singleShot(1200, self.send_to_background)

    def place_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)

    def pin_to_desktop(self) -> None:
        """Manda il widget in fondo allo z-order: visibile sul desktop ma dietro
        TUTTE le finestre, e mai attivabile (WS_EX_NOACTIVATE). Ri-asserito a
        intervalli. Solo Windows; in caso di errore resta una finestra normale."""
        if sys.platform != "win32":
            return
        try:
            u = _user32()
            hwnd = int(self.winId())
            ex = u.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, _GWL_EXSTYLE, _as_long(ex | _WS_EX_NOACTIVATE))
            self._send_window_bottom()
            self._bottom_timer.start()
            logger.info("Widget mandato sul fondo (dietro le finestre).")
        except Exception:  # noqa: BLE001 - best effort, fallback a finestra normale
            logger.exception("Invio sul fondo fallito (ignorato).")

    def _send_window_bottom(self) -> None:
        if sys.platform != "win32":
            return
        try:
            _user32().SetWindowPos(int(self.winId()), _HWND_BOTTOM, 0, 0, 0, 0, _SWP_BOTTOM)
        except Exception:  # noqa: BLE001
            pass

    def _reassert_bottom(self) -> None:
        if not self._front_mode and self.isVisible():
            self._send_window_bottom()

    def bring_to_front(self) -> None:
        """Porta i tasti in primo piano, cliccabili (richiamato dall'icona)."""
        self._bottom_timer.stop()
        if sys.platform == "win32":
            try:
                u = _user32()
                hwnd = int(self.winId())
                ex = u.GetWindowLongW(hwnd, _GWL_EXSTYLE)
                u.SetWindowLongW(hwnd, _GWL_EXSTYLE, _as_long(ex & ~_WS_EX_NOACTIVATE))
                u.SetParent(hwnd, None)  # sicurezza se mai fosse stato reparentato
            except Exception:  # noqa: BLE001
                logger.exception("Ripristino in primo piano fallito (ignorato).")
        self._front_mode = True
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.show()
        self.place_bottom_right()
        self.raise_()
        self.activateWindow()

    def send_to_background(self) -> None:
        """Rimanda il widget sul fondo (dietro le finestre)."""
        self._front_mode = False
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.show()
        self.pin_to_desktop()
        self.place_bottom_right()

    # ----- trascinamento + menu -----
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        bg_action = QAction("Manda sullo sfondo", menu)
        bg_action.triggered.connect(self.send_to_background)
        menu.addAction(bg_action)
        hide_action = QAction("Nascondi widget", menu)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        menu.exec(event.globalPos())
