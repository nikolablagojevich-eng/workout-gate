"""Stato della sessione Windows: workstation bloccata?

Euristica basata su ``OpenInputDesktop``: quando la workstation e' bloccata, il
desktop di input e' il secure desktop e l'apertura fallisce. Non e' un evento in
push (per quello servirebbe una finestra che riceve ``WM_WTSSESSION_CHANGE``), ma
e' sufficiente per il polling a 1 Hz dello scheduler. Lo sleep/resume e' gestito
implicitamente dal clamp del gap nel timer active-time.
"""

from __future__ import annotations

import ctypes
import sys

_DESKTOP_SWITCHDESKTOP = 0x0100


def is_workstation_locked() -> bool:
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    hdesk = user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)
    if not hdesk:
        return True
    user32.CloseDesktop(hdesk)
    return False


class SessionMonitor:
    """Interfaccia iniettabile (facilita i test sostituendo le callable)."""

    def __init__(self) -> None:
        self._locked_fn = is_workstation_locked

    def is_locked(self) -> bool:
        try:
            return self._locked_fn()
        except OSError:
            return False
