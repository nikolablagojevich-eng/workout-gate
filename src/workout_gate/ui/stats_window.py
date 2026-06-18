"""Finestra statistiche (sola lettura)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class StatsWindow(QDialog):
    def __init__(self, stats: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workout Gate - Statistiche")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)

        rows = [
            ("Workout completati", stats.get("workouts_completed", 0)),
            ("Squat totali", stats.get("total_squats", 0)),
            ("Streak attuale (giorni)", stats.get("streak_current", 0)),
            ("Streak piu' lungo", stats.get("streak_longest", 0)),
            ("Record ripetizioni", stats.get("personal_record_reps", 0)),
            ("Bypass d'emergenza", stats.get("bypasses", 0)),
            ("Errori tecnici", stats.get("technical_errors", 0)),
            ("Ultimo workout", stats.get("last_workout_iso") or "-"),
        ]
        for key, value in rows:
            layout.addWidget(QLabel(f"{key}: {value}"))

        close = QPushButton("Chiudi")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
