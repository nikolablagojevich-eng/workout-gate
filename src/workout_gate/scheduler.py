"""Orchestrazione del ciclo: tempo attivo -> gate -> reset -> nuovo ciclo.

Classe pura, senza Qt: ``tick(now, ...)`` riceve un orologio monotonic e lo stato
del sistema (locked, idle, sleep). Decide quando il gate e' dovuto e lo segnala
via callback. Pause, completamento workout, bypass d'emergenza ed errore tecnico
sono metodi espliciti. La GUI (``app.py``) si limita a chiamare ``tick`` da un
QTimer e a reagire alle callback. Cosi' tutta la logica di scheduling e'
testabile senza interfaccia.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from .active_time import ActiveTimeTracker


class SchedulerState(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    GATE_OPEN = "gate_open"


class Scheduler:
    def __init__(
        self,
        *,
        work_interval_seconds: float,
        idle_threshold_seconds: float,
        on_gate_due: Callable[[], None],
        max_tick_gap_seconds: float = 5.0,
        initial_accumulated: float = 0.0,
        retry_after_error_seconds: float = 600.0,
        interval_after_bypass_seconds: float = 600.0,
    ) -> None:
        self._normal_interval = work_interval_seconds
        self._tracker = ActiveTimeTracker(
            work_interval_seconds,
            max_tick_gap_seconds=max_tick_gap_seconds,
            initial_accumulated=initial_accumulated,
        )
        self._idle_threshold = idle_threshold_seconds
        self._on_gate_due = on_gate_due
        self._retry_error = retry_after_error_seconds
        self._bypass_interval = interval_after_bypass_seconds

        self._gate_open = False
        self._paused_until: float | None = None
        self._paused_forever = False

    # ----- stato -----
    @property
    def state(self) -> SchedulerState:
        if self._gate_open:
            return SchedulerState.GATE_OPEN
        if self.is_paused:
            return SchedulerState.PAUSED
        return SchedulerState.ACTIVE

    @property
    def is_paused(self) -> bool:
        return self._paused_forever or self._paused_until is not None

    @property
    def accumulated_seconds(self) -> float:
        return self._tracker.accumulated

    @property
    def remaining_seconds(self) -> float:
        return self._tracker.remaining()

    @property
    def paused_until_monotonic(self) -> float | None:
        return self._paused_until

    @property
    def gate_open(self) -> bool:
        return self._gate_open

    # ----- ciclo principale -----
    def tick(
        self,
        now: float,
        *,
        locked: bool = False,
        idle_seconds: float = 0.0,
        asleep: bool = False,
    ) -> None:
        # Scadenza pausa a tempo.
        if self._paused_until is not None and now >= self._paused_until:
            self._paused_until = None

        if self._gate_open or self.is_paused:
            # Tiene fresco l'orologio interno ma non accumula.
            self._tracker.tick(now, active=False)
            return

        active = (not locked) and (not asleep) and (idle_seconds < self._idle_threshold)
        self._tracker.tick(now, active=active)

        if self._tracker.reached():
            self._gate_open = True
            self._on_gate_due()

    # ----- comandi -----
    def workout_now(self) -> None:
        """Apre subito il gate (voce di tray 'Avvia workout adesso')."""
        if self._gate_open:
            return
        self._gate_open = True
        self._on_gate_due()

    def on_workout_completed(self) -> None:
        """Workout completato: azzera, ripristina l'intervallo normale, riparte."""
        self._tracker.set_work_interval(self._normal_interval)
        self._tracker.reset()
        self._tracker.detach_clock()
        self._gate_open = False

    def on_emergency_bypass(self) -> None:
        """Bypass d'emergenza: niente debito, riprova dopo l'intervallo ridotto."""
        self._tracker.reset()
        self._tracker.set_work_interval(self._bypass_interval)
        self._tracker.detach_clock()
        self._gate_open = False

    def on_technical_error(self) -> None:
        """Fail-open: chiudi il gate senza debito, riprova dopo l'intervallo di retry."""
        self._tracker.reset()
        self._tracker.set_work_interval(self._retry_error)
        self._tracker.detach_clock()
        self._gate_open = False

    def pause(self, now: float, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("La durata della pausa deve essere > 0")
        self._paused_forever = False
        self._paused_until = now + seconds
        self._tracker.detach_clock()

    def pause_until_login(self) -> None:
        self._paused_forever = True
        self._paused_until = None
        self._tracker.detach_clock()

    def resume(self) -> None:
        self._paused_forever = False
        self._paused_until = None
        self._tracker.detach_clock()

    def reset_timer(self) -> None:
        """Azzera il tempo attivo accumulato (comando manuale, con conferma a monte)."""
        self._tracker.reset()
        self._tracker.detach_clock()

    # ----- persistenza -----
    def load_accumulated(self, seconds: float) -> None:
        self._tracker.load(seconds)
