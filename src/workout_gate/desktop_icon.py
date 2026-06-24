"""Icona/collegamento sul desktop per richiamare il widget ON/OFF in primo piano.

Genera un file ``.ico`` (simbolo di accensione) e crea un collegamento sul Desktop
che lancia ``workout-gate widget``, il quale porta i tasti ON/OFF davanti.
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path

from .paths import data_dir

logger = logging.getLogger(__name__)

SHORTCUT_NAME = "Workout Gate ON-OFF.lnk"


def icon_path() -> Path:
    return data_dir() / "widget-icon.ico"


def _render_png(size: int = 64) -> bytes:
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
    pen.setColor(QColor("#3ad36a"))
    pen.setWidth(max(3, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.28
    p.drawArc(int(m), int(m), int(size - 2 * m), int(size - 2 * m), 125 * 16, 290 * 16)
    cx = int(size / 2)
    p.drawLine(cx, int(size * 0.18), cx, int(size * 0.5))
    p.end()

    # Salva su file temporaneo .png (Qt deduce il formato dall'estensione).
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


def ensure_icon_file(size: int = 64) -> Path:
    """Genera il .ico se manca (richiede una QGuiApplication attiva)."""
    path = icon_path()
    if path.exists():
        return path
    try:
        path.write_bytes(_build_ico(_render_png(size), size))
        logger.info("Icona widget generata: %s", path)
    except Exception:  # noqa: BLE001
        logger.exception("Generazione icona fallita (ignorata).")
    return path


def _desktop_dir() -> Path:
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    return Path(shell.SpecialFolders("Desktop"))


def shortcut_path() -> Path:
    return _desktop_dir() / SHORTCUT_NAME


def install_desktop_shortcut() -> Path:
    import win32com.client

    from .autostart import _pythonw

    ico = ensure_icon_file()
    target = shortcut_path()
    shell = win32com.client.Dispatch("WScript.Shell")
    link = shell.CreateShortcut(str(target))
    link.TargetPath = _pythonw()
    link.Arguments = "-m workout_gate widget"
    link.WorkingDirectory = str(Path.home())
    link.WindowStyle = 7
    if ico.exists():
        link.IconLocation = f"{ico},0"
    link.Description = "Workout Gate ON/OFF"
    link.save()
    logger.info("Collegamento sul desktop creato: %s", target)
    return target


def remove_desktop_shortcut() -> bool:
    target = shortcut_path()
    if target.exists():
        target.unlink()
        return True
    return False
