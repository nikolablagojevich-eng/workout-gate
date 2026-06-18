"""Logica del bypass d'emergenza: tieni premuto N secondi, poi scegli un motivo.

Pura e testabile (nessuna UI). La GUI chiama ``start``/``cancel`` sui press/release
del pulsante e ``progress(now)`` per il countdown. Il bypass non e' immediato ne'
accidentale, ma deve restare sempre raggiungibile.
"""

from __future__ import annotations

from dataclasses import dataclass

# Categorie registrabili (solo la categoria + il timestamp vengono salvati).
BYPASS_CATEGORIES: tuple[str, ...] = (
    "problema_fisico",
    "dolore",
    "vertigini",
    "webcam_non_funzionante",
    "situazione_urgente",
    "ambiente_non_adatto",
    "altro",
)

BYPASS_CATEGORY_LABELS: dict[str, str] = {
    "problema_fisico": "Problema fisico",
    "dolore": "Dolore",
    "vertigini": "Vertigini",
    "webcam_non_funzionante": "Webcam non funzionante",
    "situazione_urgente": "Situazione urgente",
    "ambiente_non_adatto": "Ambiente non adatto",
    "altro": "Altro",
}


@dataclass(frozen=True)
class HoldProgress:
    holding: bool
    elapsed: float
    remaining: float
    ready: bool


class HoldToConfirm:
    def __init__(self, hold_seconds: float) -> None:
        if hold_seconds <= 0:
            raise ValueError("hold_seconds deve essere > 0")
        self.hold_seconds = hold_seconds
        self._start: float | None = None

    def start(self, now: float) -> None:
        if self._start is None:
            self._start = now

    def cancel(self) -> None:
        self._start = None

    @property
    def holding(self) -> bool:
        return self._start is not None

    def progress(self, now: float) -> HoldProgress:
        if self._start is None:
            return HoldProgress(
                holding=False, elapsed=0.0, remaining=self.hold_seconds, ready=False
            )
        elapsed = max(0.0, now - self._start)
        remaining = max(0.0, self.hold_seconds - elapsed)
        return HoldProgress(
            holding=True,
            elapsed=elapsed,
            remaining=remaining,
            ready=elapsed >= self.hold_seconds,
        )
