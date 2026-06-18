"""Canale comandi CLI -> istanza in esecuzione, e file di stato app -> CLI.

Meccanismo semplice e robusto basato su file nella data dir:
* ``commands.jsonl``: la CLI appende comandi (pause/resume/workout-now/quit);
  l'app li drena a ogni tick.
* ``status.json``: l'app scrive lo stato corrente; la CLI lo legge per ``status``.

Niente socket o porte: meno superficie, nessun conflitto, funziona senza rete.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Any

from .paths import data_dir

logger = logging.getLogger(__name__)


def _commands_file():
    return data_dir() / "commands.jsonl"


def _status_file():
    return data_dir() / "status.json"


def send_command(action: str, **payload: Any) -> None:
    record = {"action": action, "ts": time.time(), **payload}
    with open(_commands_file(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def drain_commands() -> list[dict[str, Any]]:
    path = _commands_file()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("", encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def write_status(status: dict[str, Any]) -> None:
    status = {**status, "ts": time.time()}
    path = _status_file()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="status.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(status, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_status() -> dict[str, Any] | None:
    path = _status_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_running(max_age_seconds: float = 5.0) -> bool:
    """Euristica: l'app e' attiva se ha aggiornato lo status di recente."""
    st = read_status()
    if not st:
        return False
    return (time.time() - st.get("ts", 0)) <= max_age_seconds
