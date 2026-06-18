"""Avvio automatico al login tramite shortcut nella cartella Startup di Windows.

Nessun privilegio admin: si crea un ``.lnk`` in
``%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup`` che lancia
``pythonw -m workout_gate run`` (senza console). Rimozione = cancellazione del lnk.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SHORTCUT_NAME = "WorkoutGate.lnk"


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return _startup_dir() / SHORTCUT_NAME


def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def is_enabled() -> bool:
    return shortcut_path().exists()


def install() -> Path:
    import win32com.client  # pywin32

    target = shortcut_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shell = win32com.client.Dispatch("WScript.Shell")
    link = shell.CreateShortcut(str(target))
    link.TargetPath = _pythonw()
    link.Arguments = "-m workout_gate run"
    link.WorkingDirectory = str(Path.home())
    link.WindowStyle = 7  # minimizzato
    link.Description = "Workout Gate"
    link.save()
    logger.info("Autostart installato: %s", target)
    return target


def remove() -> bool:
    target = shortcut_path()
    if target.exists():
        target.unlink()
        logger.info("Autostart rimosso: %s", target)
        return True
    return False
