"""Icone/collegamenti sul desktop per accendere e spegnere il Workout Gate.

Crea due icone dirette:
  - "Workout ON"  (simbolo power verde) -> ``workout-gate on``  (riprende)
  - "Workout OFF" (simbolo power rosso) -> ``workout-gate off`` (sospende)
Generano i propri file ``.ico`` (nessuna dipendenza grafica esterna).
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path

from .paths import data_dir

logger = logging.getLogger(__name__)

ON_SHORTCUT = "Workout ON.lnk"
OFF_SHORTCUT = "Workout OFF.lnk"
_LEGACY_SHORTCUT = "Workout Gate ON-OFF.lnk"  # vecchia icona "summon", da rimuovere

_GREEN = "#3ad36a"
_RED = "#e74c3c"


def _icon_path(name: str) -> Path:
    return data_dir() / f"{name}.ico"


def _render_png(size: int, color: str) -> bytes:
    import os
    import tempfile

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    pix = QPixmap(size, size)
    pix.fill(QColor("transparent"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#161616"))
    p.setPen(QColor("#3a3a3a"))
    p.drawRoundedRect(2, 2, size - 4, size - 4, 12, 12)

    pen = p.pen()
    pen.setColor(QColor(color))
    pen.setWidth(max(3, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.28
    p.drawArc(int(m), int(m), int(size - 2 * m), int(size - 2 * m), 125 * 16, 290 * 16)
    cx = int(size / 2)
    p.drawLine(cx, int(size * 0.18), cx, int(size * 0.5))
    p.end()

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        if not pix.save(tmp):
            raise RuntimeError("salvataggio PNG fallito")
        return Path(tmp).read_bytes()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _build_ico(png: bytes, size: int) -> bytes:
    dim = 0 if size >= 256 else size
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), 22)
    return header + entry + png


def ensure_icon(name: str, color: str, size: int = 64) -> Path:
    path = _icon_path(name)
    if path.exists():
        return path
    try:
        path.write_bytes(_build_ico(_render_png(size, color), size))
        logger.info("Icona %s generata.", name)
    except Exception:  # noqa: BLE001
        logger.exception("Generazione icona %s fallita (ignorata).", name)
    return path


def ensure_icons() -> None:
    """Genera i file .ico ON/OFF se mancano (richiede una QGuiApplication)."""
    ensure_icon("workout-on", _GREEN)
    ensure_icon("workout-off", _RED)


def _desktop_dir() -> Path:
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    return Path(shell.SpecialFolders("Desktop"))


def _make_shortcut(filename: str, action: str, ico: Path, description: str) -> Path:
    import win32com.client

    from .autostart import _pythonw

    target = _desktop_dir() / filename
    shell = win32com.client.Dispatch("WScript.Shell")
    link = shell.CreateShortcut(str(target))
    link.TargetPath = _pythonw()
    link.Arguments = f"-m workout_gate {action}"
    link.WorkingDirectory = str(Path.home())
    link.WindowStyle = 7  # minimizzato, niente console
    if ico.exists():
        link.IconLocation = f"{ico},0"
    link.Description = description
    link.save()
    logger.info("Collegamento creato: %s", target)
    return target


def install_onoff_icons() -> list[Path]:
    """Crea le icone dirette ON (verde) e OFF (rosso) sul desktop."""
    on_ico = ensure_icon("workout-on", _GREEN)
    off_ico = ensure_icon("workout-off", _RED)
    created = [
        _make_shortcut(ON_SHORTCUT, "on", on_ico, "Accendi Workout Gate"),
        _make_shortcut(OFF_SHORTCUT, "off", off_ico, "Spegni Workout Gate"),
    ]
    # Rimuove la vecchia icona unica, se presente.
    legacy = _desktop_dir() / _LEGACY_SHORTCUT
    if legacy.exists():
        try:
            legacy.unlink()
        except OSError:
            pass
    return created


def remove_onoff_icons() -> bool:
    removed = False
    for name in (ON_SHORTCUT, OFF_SHORTCUT, _LEGACY_SHORTCUT):
        target = _desktop_dir() / name
        if target.exists():
            try:
                target.unlink()
                removed = True
            except OSError:
                pass
    return removed
