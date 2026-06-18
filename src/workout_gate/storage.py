"""Persistenza su JSON con scrittura atomica e recupero da file corrotto.

v1 usa un singolo file JSON (non SQLite): meno superficie, nessuna migrazione.
Si salvano SOLO dati numerici/operativi. Mai video, immagini, frame o landmark.

Scrittura atomica: si scrive su un file temporaneo e si fa ``os.replace`` (atomico
su Windows e POSIX). Se il file e' corrotto al caricamento, si fa il backup del
corrotto e si riparte dai default: lo storage non deve mai causare un lockout.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "accumulated_active_seconds": 0.0,
        "last_persisted_iso": None,
        "last_workout_iso": None,
        "last_workout_date": None,
        "workouts_completed": 0,
        "total_squats": 0,
        "streak_current": 0,
        "streak_longest": 0,
        "personal_record_reps": 0,
        "bypasses": 0,
        "technical_errors": 0,
        "pauses": 0,
        "sessions": [],  # storico recente (lista di dict compatti)
    }


class JsonStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_state()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.error("Storage corrotto (%s): backup e reset ai default.", exc)
            self._backup_corrupt()
            return default_state()
        if not isinstance(raw, dict):
            logger.error("Storage non e' un oggetto JSON: reset ai default.")
            self._backup_corrupt()
            return default_state()
        return self._migrate(raw)

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            # Pulizia del temporaneo in caso di errore: niente .tmp orfani.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def update(self, **changes: Any) -> dict[str, Any]:
        data = self.load()
        data.update(changes)
        self.save(data)
        return data

    def _backup_corrupt(self) -> None:
        try:
            backup = self.path.with_suffix(self.path.suffix + ".corrupt")
            os.replace(self.path, backup)
            logger.info("File corrotto spostato in %s", backup)
        except OSError:
            logger.warning("Impossibile fare il backup del file corrotto.")

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        version = data.get("schema_version", 0)
        if version == SCHEMA_VERSION:
            merged = default_state()
            merged.update(data)
            return merged
        # Migrazione in avanti: parte dai default e copia le chiavi note.
        logger.info("Migrazione storage da schema v%s a v%s", version, SCHEMA_VERSION)
        merged = default_state()
        for key in merged:
            if key in data and key != "schema_version":
                merged[key] = data[key]
        merged["schema_version"] = SCHEMA_VERSION
        return merged
