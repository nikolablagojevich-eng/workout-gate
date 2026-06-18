"""Finestra impostazioni (sola lettura + apertura cartella config).

La configurazione vive nel file YAML: questa finestra mostra i valori effettivi e
permette di aprire la cartella per modificarli. I parametri privacy sono forzati
e non modificabili da qui (ne' da file).
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..config import AppConfig


class SettingsWindow(QDialog):
    def __init__(self, cfg: AppConfig, config_file: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workout Gate - Impostazioni")
        self.setMinimumWidth(420)
        self._config_file = config_file
        layout = QVBoxLayout(self)

        rows = [
            ("Intervallo lavoro", f"{cfg.timer.work_interval_minutes:.0f} min"),
            ("Soglia inattivita'", f"{cfg.timer.idle_threshold_seconds:.0f} s"),
            ("Ripetizioni richieste", str(cfg.workout.required_repetitions)),
            ("Soglia eretto / fondo",
             f"{cfg.vision.standing_knee_angle_degrees:.0f} / "
             f"{cfg.vision.bottom_knee_angle_degrees:.0f} gradi"),
            ("Webcam (index)", str(cfg.vision.camera_index)),
            ("Avvio al login", "si" if cfg.startup.start_at_login else "no"),
        ]
        for key, value in rows:
            layout.addWidget(QLabel(f"{key}: {value}"))

        layout.addWidget(QLabel("\nPrivacy (forzata, non modificabile):"))
        layout.addWidget(
            QLabel("Nessun video / immagine / frame salvato. Nessuna rete, telemetria, analytics.")
        )
        layout.addWidget(QLabel(f"\nFile config: {config_file}"))

        open_btn = QPushButton("Apri cartella configurazione")
        open_btn.clicked.connect(self._open_folder)
        layout.addWidget(open_btn)

        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _open_folder(self) -> None:
        folder = str(self._config_file.parent)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]  # solo Windows
        except (AttributeError, OSError):
            pass
