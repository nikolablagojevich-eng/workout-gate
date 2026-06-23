"""Widget desktop con interruttore retro ON/OFF.

Piccola finestra senza bordi, sempre in primo piano, trascinabile, con due
pulsanti vecchio stile. ON tiene attivo il counter; OFF lo spegne (pausa a tempo
indeterminato) per quando non ci si puo' permettere il blocco schermo (riunioni,
presentazioni). Emette i segnali ``turnedOn``/``turnedOff``: la logica vive
nell'app/scheduler, qui solo presentazione e stato.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setObjectName("WidgetRoot")
        self.setStyleSheet(_PANEL)
        self.setFixedSize(196, 104)
        self._drag_offset: QPoint | None = None

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
        self._on.clicked.connect(lambda: self.turnedOn.emit())
        self._off = QPushButton("OFF")
        self._off.setObjectName("Off")
        self._off.clicked.connect(lambda: self.turnedOff.emit())
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

    def place_bottom_right(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)

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
        hide_action = QAction("Nascondi widget", menu)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        menu.exec(event.globalPos())
