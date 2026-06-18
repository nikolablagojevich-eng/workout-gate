"""Rilevamento inattivita' input tramite l'API Windows ``GetLastInputInfo``.

Importabile anche su piattaforme non-Windows (dove ritorna sempre 0 = attivo):
serve a non rompere i test e a permettere lo sviluppo cross-platform.
"""

from __future__ import annotations

import ctypes
import sys


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    """Secondi dall'ultimo input di mouse/tastiera (a livello di sistema)."""
    if sys.platform != "win32":
        return 0.0
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    tick = kernel32.GetTickCount() & 0xFFFFFFFF
    elapsed_ms = (tick - lii.dwTime) & 0xFFFFFFFF
    return max(0.0, elapsed_ms / 1000.0)


class IdleDetector:
    def __init__(self, threshold_seconds: float) -> None:
        self.threshold = threshold_seconds

    def idle_seconds(self) -> float:
        return get_idle_seconds()

    def is_idle(self) -> bool:
        return self.idle_seconds() >= self.threshold
