"""System tray: stato, menu e azioni. La logica vive nello scheduler/app, qui solo
presentazione e instradamento ai callback iniettati."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QInputDialog, QMenu, QSystemTrayIcon


def create_icon(color: str = "#4A6FA5") -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor("transparent"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor("#0D1B2A"))
    painter.drawRoundedRect(6, 6, 52, 52, 14, 14)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(22)
    painter.setFont(font)
    painter.drawText(pix.rect(), 0x84, "WG")  # AlignCenter
    painter.end()
    return QIcon(pix)


@dataclass
class TrayCallbacks:
    workout_now: Callable[[], None]
    pause_minutes: Callable[[int], None]
    pause_until_login: Callable[[], None]
    resume: Callable[[], None]
    settings: Callable[[], None]
    stats: Callable[[], None]
    calibrate: Callable[[], None]
    test_camera: Callable[[], None]
    doctor: Callable[[], None]
    quit: Callable[[], None]


class Tray:
    def __init__(self, callbacks: TrayCallbacks) -> None:
        self.cb = callbacks
        self.icon = QSystemTrayIcon(create_icon())
        self.icon.setToolTip("Workout Gate")
        self._menu = QMenu()
        self._build_menu()
        self.icon.setContextMenu(self._menu)

    def _build_menu(self) -> None:
        self._status_action = QAction("Avvio...")
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()

        self._add(self._menu, "Avvia workout adesso", self.cb.workout_now)

        pause_menu = self._menu.addMenu("Pausa")
        self._add(pause_menu, "15 minuti", lambda: self.cb.pause_minutes(15))
        self._add(pause_menu, "30 minuti", lambda: self.cb.pause_minutes(30))
        self._add(pause_menu, "1 ora", lambda: self.cb.pause_minutes(60))
        self._add(pause_menu, "Personalizzata...", self._custom_pause)
        self._add(pause_menu, "Fino al prossimo login", self.cb.pause_until_login)

        self._add(self._menu, "Riprendi", self.cb.resume)
        self._menu.addSeparator()

        self._add(self._menu, "Impostazioni", self.cb.settings)
        self._add(self._menu, "Statistiche", self.cb.stats)
        self._add(self._menu, "Calibra webcam", self.cb.calibrate)
        self._add(self._menu, "Test webcam", self.cb.test_camera)
        self._add(self._menu, "Diagnostica", self.cb.doctor)
        self._menu.addSeparator()
        self._add(self._menu, "Esci", self.cb.quit)

    @staticmethod
    def _add(menu: QMenu, text: str, handler: Callable[[], None]) -> QAction:
        action = QAction(text, menu)
        action.triggered.connect(lambda _checked=False: handler())
        menu.addAction(action)
        return action

    def _custom_pause(self) -> None:
        minutes, ok = QInputDialog.getInt(
            None, "Pausa personalizzata", "Minuti di pausa:", 20, 1, 1440, 5
        )
        if ok:
            self.cb.pause_minutes(minutes)

    def set_status(self, text: str, *, paused: bool = False, error: bool = False) -> None:
        self._status_action.setText(text)
        self.icon.setToolTip(f"Workout Gate - {text}")
        color = "#C98B8B" if error else ("#C9A24A" if paused else "#4A6FA5")
        self.icon.setIcon(create_icon(color))

    def show(self) -> None:
        self.icon.show()

    def hide(self) -> None:
        self.icon.hide()
