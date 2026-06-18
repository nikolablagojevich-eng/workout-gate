"""Finestra del Workout Gate: self-view a sinistra, stato e contatore a destra.

Mostra il feed webcam live con scheletro (cio' che Nik vuole vedere mentre fa gli
squat), il contatore N/10, la fase, il feedback dinamico, la confidenza, la
durata, lo stato webcam, il banner privacy, l'avvertenza di sicurezza e il
bypass d'emergenza (tieni premuto). Intercetta ALT+F4 e la chiusura: il gate si
chiude solo per completamento o bypass.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..gate.emergency_bypass import (
    BYPASS_CATEGORIES,
    BYPASS_CATEGORY_LABELS,
    HoldToConfirm,
)

PRIVACY_TEXT = (
    "La webcam verifica il movimento localmente. "
    "Nessun video, immagine o fotogramma viene registrato o salvato."
)
SAFETY_TEXT = (
    "Interrompi immediatamente in caso di dolore, vertigini, perdita di equilibrio "
    "o malessere. Workout Gate non e' un dispositivo medico."
)

_STYLE = """
QWidget#GateRoot { background-color: #0D1B2A; }
QLabel { color: #E8E6E1; }
QLabel#Title { font-size: 30px; font-weight: 700; }
QLabel#Subtitle { font-size: 17px; color: #9DB2C8; }
QLabel#Counter { font-size: 96px; font-weight: 800; color: #FFFFFF; }
QLabel#Phase { font-size: 22px; color: #4A6FA5; font-weight: 600; }
QLabel#Feedback { font-size: 24px; color: #FFD479; font-weight: 600; }
QLabel#Meta { font-size: 14px; color: #9DB2C8; }
QLabel#Privacy { font-size: 12px; color: #7E8C9E; }
QLabel#Safety { font-size: 12px; color: #C98B8B; }
QLabel#Video { background-color: #060E16; border: 1px solid #1B2A3A; }
QPushButton#Bypass {
    background-color: #2A1B1B; color: #C98B8B; border: 1px solid #5A3A3A;
    border-radius: 8px; padding: 10px; font-size: 13px; min-height: 36px;
}
QPushButton#Bypass:pressed { background-color: #5A2A2A; color: #FFFFFF; }
"""


class WorkoutWindow(QWidget):
    bypassConfirmed = Signal(str)  # categoria

    def __init__(self, required_reps: int, bypass_hold_seconds: float = 10.0) -> None:
        super().__init__()
        self.setObjectName("GateRoot")
        self.required = required_reps
        self._start_ts = time.monotonic()
        self._hold = HoldToConfirm(bypass_hold_seconds)
        self._completed = False
        self._last_conf = 0.0
        self._last_webcam = "avvio"

        self.setStyleSheet(_STYLE)
        self._build_ui()

        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(50)
        self._hold_timer.timeout.connect(self._update_hold)

        self._duration_timer = QTimer(self)
        self._duration_timer.setInterval(250)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.start()

    # ----- costruzione UI -----
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(32)

        self.video = QLabel("Avvio webcam...")
        self.video.setObjectName("Video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(640, 480)
        root.addWidget(self.video, stretch=3)

        right = QVBoxLayout()
        right.setSpacing(14)
        root.addLayout(right, stretch=2)

        title = QLabel("Workout Gate")
        title.setObjectName("Title")
        right.addWidget(title)

        subtitle = QLabel(f"Completa {self.required} squat per continuare")
        subtitle.setObjectName("Subtitle")
        right.addWidget(subtitle)

        self.counter = QLabel(f"0 / {self.required}")
        self.counter.setObjectName("Counter")
        right.addWidget(self.counter)

        self.missing = QLabel(f"Mancanti: {self.required}")
        self.missing.setObjectName("Meta")
        right.addWidget(self.missing)

        self.phase = QLabel("Fase: -")
        self.phase.setObjectName("Phase")
        right.addWidget(self.phase)

        self.feedback = QLabel("Inquadra tutto il corpo")
        self.feedback.setObjectName("Feedback")
        self.feedback.setWordWrap(True)
        right.addWidget(self.feedback)

        self.meta = QLabel("Confidenza: -   Webcam: avvio   Durata: 0s")
        self.meta.setObjectName("Meta")
        right.addWidget(self.meta)

        right.addStretch(1)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#1B2A3A;")
        right.addWidget(line)

        privacy = QLabel(PRIVACY_TEXT)
        privacy.setObjectName("Privacy")
        privacy.setWordWrap(True)
        right.addWidget(privacy)

        safety = QLabel(SAFETY_TEXT)
        safety.setObjectName("Safety")
        safety.setWordWrap(True)
        right.addWidget(safety)

        self.bypass_btn = QPushButton("Bypass d'emergenza (tieni premuto 10s)")
        self.bypass_btn.setObjectName("Bypass")
        self.bypass_btn.pressed.connect(self._bypass_pressed)
        self.bypass_btn.released.connect(self._bypass_released)
        right.addWidget(self.bypass_btn)

    # ----- aggiornamento da worker -----
    def update_view(self, step, qimage: QImage) -> None:
        if not qimage.isNull():
            pix = QPixmap.fromImage(qimage)
            self.video.setPixmap(
                pix.scaled(
                    self.video.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        res = step.counter
        count = step.count
        self.counter.setText(f"{count} / {self.required}")
        self.missing.setText(f"Mancanti: {max(0, self.required - count)}")
        self.phase.setText(f"Fase: {res.phase_label}")
        self.feedback.setText(res.feedback)
        self._last_conf = res.confidence
        self._last_webcam = "attiva" if step.subject_present else "nessun corpo"
        self._render_meta()

    def _render_meta(self) -> None:
        elapsed = int(time.monotonic() - self._start_ts)
        self.meta.setText(
            f"Confidenza: {self._last_conf * 100:.0f}%   "
            f"Webcam: {self._last_webcam}   Durata: {elapsed}s"
        )

    def _update_duration(self) -> None:
        self._render_meta()

    def show_completion(self) -> None:
        self._completed = True
        self.counter.setText(f"{self.required} / {self.required}")
        self.missing.setText("Mancanti: 0")
        self.feedback.setText("Workout completato")
        self.phase.setText("Fase: fatto")

    # ----- bypass (tieni premuto) -----
    def _bypass_pressed(self) -> None:
        self._hold.start(time.monotonic())
        self._hold_timer.start()

    def _bypass_released(self) -> None:
        self._hold.cancel()
        self._hold_timer.stop()
        self.bypass_btn.setText("Bypass d'emergenza (tieni premuto 10s)")

    def _update_hold(self) -> None:
        prog = self._hold.progress(time.monotonic())
        if prog.ready:
            self._hold_timer.stop()
            self._hold.cancel()
            self.bypass_btn.setText("Bypass d'emergenza (tieni premuto 10s)")
            self._ask_bypass_reason()
            return
        self.bypass_btn.setText(f"Continua a tenere premuto... {prog.remaining:.0f}s")

    def _ask_bypass_reason(self) -> None:
        labels = [BYPASS_CATEGORY_LABELS[c] for c in BYPASS_CATEGORIES]
        choice, ok = QInputDialog.getItem(
            self, "Bypass d'emergenza", "Motivo:", labels, 0, False
        )
        if ok and choice:
            category = BYPASS_CATEGORIES[labels.index(choice)]
            self.bypassConfirmed.emit(category)

    # ----- blocco chiusura -----
    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Intercetta ALT+F4 ed Esc nella propria finestra.
        if event.key() == Qt.Key.Key_F4 and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            event.ignore()
            return
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if self._completed:
            event.accept()
        else:
            # Chiusura consentita solo via completamento o bypass.
            event.ignore()
