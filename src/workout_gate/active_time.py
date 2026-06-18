"""Timer del tempo di utilizzo attivo, basato su tick.

Principio chiave: NON si calcola mai ``elapsed = now - start``. Si accumula un
contatore solo finche' l'utente e' attivo, sommando piccoli delta a ogni tick.
Cosi' sleep, lock, cambio dell'orologio di sistema e spegnimento diventano
non-problemi per costruzione: se non si tick-a (o il delta e' troppo grande,
segno di una sospensione), il tempo non sale.

Il valore accumulato e' l'unico dato da persistere: ``time.monotonic()`` si
azzera a ogni avvio del processo, quindi non lo si memorizza mai; si ricarica
l'accumulato dallo storage e si riprende da li'.
"""

from __future__ import annotations


class ActiveTimeTracker:
    def __init__(
        self,
        work_interval_seconds: float,
        *,
        max_tick_gap_seconds: float = 5.0,
        initial_accumulated: float = 0.0,
    ) -> None:
        if work_interval_seconds <= 0:
            raise ValueError("work_interval_seconds deve essere > 0")
        self._work = work_interval_seconds
        self._max_gap = max_tick_gap_seconds
        self._acc = max(0.0, initial_accumulated)
        self._last_t: float | None = None

    def tick(self, now: float, *, active: bool) -> float:
        """Avanza il timer. Ritorna i secondi effettivamente accumulati in questo tick.

        ``now`` deve provenire da un orologio monotonic. ``active`` e' calcolato
        dal chiamante (unlocked AND non idle AND non in pausa AND non in sleep).
        Un delta > ``max_tick_gap`` indica un buco (sospensione/processo fermo) e
        non viene conteggiato.
        """
        if self._last_t is None:
            self._last_t = now
            return 0.0
        delta = now - self._last_t
        self._last_t = now
        if active and 0.0 < delta <= self._max_gap:
            self._acc += delta
            return delta
        return 0.0

    @property
    def accumulated(self) -> float:
        return self._acc

    @property
    def work_interval(self) -> float:
        return self._work

    def reached(self) -> bool:
        return self._acc >= self._work

    def remaining(self) -> float:
        return max(0.0, self._work - self._acc)

    def reset(self) -> None:
        """Azzera l'accumulato (es. dopo un workout completato). Non tocca il clock."""
        self._acc = 0.0

    def load(self, accumulated: float) -> None:
        self._acc = max(0.0, accumulated)

    def set_work_interval(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("work_interval deve essere > 0")
        self._work = seconds

    def detach_clock(self) -> None:
        """Dimentica l'ultimo tick (es. dopo resume da sleep): il prossimo tick
        ricomincia a misurare il delta da zero, senza conteggiare il buco."""
        self._last_t = None
