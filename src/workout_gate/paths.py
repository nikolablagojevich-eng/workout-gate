"""Percorsi dei dati applicativi (per-utente, nessun privilegio admin)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "WorkoutGate"


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    d = root / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return data_dir() / "config.yaml"


def state_path() -> Path:
    return data_dir() / "workout_gate_state.json"


def lock_path() -> Path:
    return data_dir() / "workout_gate.lock"


def log_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d
