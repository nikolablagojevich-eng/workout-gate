"""Conteggio squat dal movimento verticale del busto (spalle).

Pensato per webcam che inquadrano solo testa e spalle (laptop): uno squat abbassa
tutto il busto, e la posizione verticale delle spalle (y, cresce verso il basso)
e' un segnale netto e sempre visibile. Macchina a stati esplicita
STANDING -> DESCENDING -> BOTTOM -> ASCENDING -> STANDING, con isteresi, debounce,
durata realistica e anti-doppio-conteggio.

Baseline = posizione "in piedi", stimata come **percentile basso della y delle
spalle in una finestra mobile** (ultimi N secondi). Questa scelta e' robusta:
non insegue un valore singolo (che potrebbe agganciarsi a un picco transitorio e
restare incastrato), e si auto-corregge perche' i campioni vecchi escono dalla
finestra. La "profondita'" e' il calo sotto la baseline.

Il conteggio e' MONOTONO durante la sessione: corpo assente, soggetto cambiato o
squat sbagliato resettano solo la ripetizione in corso, mai il totale.
"""

from __future__ import annotations

from collections import deque

from .squat_state import CounterResult, Feedback, SquatState


class VerticalRepCounter:
    def __init__(
        self,
        *,
        min_drop: float = 0.08,
        hysteresis: float = 0.02,
        min_visibility: float = 0.6,
        standing_stability_seconds: float = 0.15,
        min_cycle_seconds: float = 0.4,
        max_cycle_seconds: float = 8.0,
        baseline_window_seconds: float = 4.0,
        baseline_percentile: float = 0.25,
    ) -> None:
        self.min_drop = min_drop
        self.h = hysteresis
        self.min_visibility = min_visibility
        self.stability = standing_stability_seconds
        self.min_cycle = min_cycle_seconds
        self.max_cycle = max_cycle_seconds
        self.window_seconds = baseline_window_seconds
        self.pct = baseline_percentile

        self.descend_enter = self.min_drop * 0.35
        self.bottom_enter = self.min_drop
        self.up_exit = self.min_drop - self.h
        self.stand_return = self.min_drop * 0.25
        self._meaningful = self.min_drop * 0.5

        self.reset_all()

    # ----- stato -----
    def reset_all(self) -> None:
        self._state = SquatState.WAITING_FOR_BODY
        self._count = 0
        self._window: deque[tuple[float, float]] = deque()
        self._baseline: float | None = None
        self._standing_since: float | None = None
        self._reset_rep()

    def soft_reset(self) -> None:
        """Reset SOLO della ripetizione in corso e dello stato. Mantiene conteggio
        e finestra baseline: il totale non si annulla mai durante la sessione."""
        self._state = SquatState.WAITING_FOR_BODY
        self._standing_since = None
        self._reset_rep()

    def _reset_rep(self) -> None:
        self._descent_start: float | None = None
        self._reached_bottom = False
        self._valid_start = False
        self._max_drop = 0.0

    def _enter_standing(self, t: float) -> None:
        self._state = SquatState.STANDING
        self._standing_since = t
        self._reset_rep()

    @property
    def count(self) -> int:
        return self._count

    @property
    def state(self) -> SquatState:
        return self._state

    @property
    def baseline(self) -> float | None:
        return self._baseline

    def _result(
        self,
        feedback: str,
        confidence: float,
        *,
        just_completed: bool = False,
        rejected: bool = False,
    ) -> CounterResult:
        return CounterResult(
            state=self._state,
            rep_count=self._count,
            just_completed=just_completed,
            rejected=rejected,
            feedback=feedback,
            confidence=confidence,
            depth_reached=self._reached_bottom,
        )

    def _update_baseline(self, t: float, y: float) -> float:
        """Baseline = percentile basso della y su una finestra mobile. Robusta ai
        picchi, si auto-corregge (i campioni vecchi escono)."""
        self._window.append((t, y))
        cutoff = t - self.window_seconds
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()
        ys = sorted(v for _, v in self._window)
        k = max(0, min(len(ys) - 1, round(self.pct * (len(ys) - 1))))
        return ys[k]

    # ----- aggiornamento per-frame -----
    def update(
        self,
        *,
        timestamp: float,
        body_present: bool,
        signal_y: float,
        visibility: float,
    ) -> CounterResult:
        conf = visibility

        if not body_present or visibility < self.min_visibility:
            if self._state is not SquatState.WAITING_FOR_BODY:
                self.soft_reset()
            return self._result(Feedback.BODY_NOT_VISIBLE, conf)

        t = timestamp
        self._baseline = self._update_baseline(t, signal_y)
        drop = signal_y - self._baseline

        if self._state is SquatState.WAITING_FOR_BODY:
            self._enter_standing(t)
            return self._result(Feedback.POSITION_DETECTED, conf)

        if self._state is SquatState.STANDING:
            assert self._standing_since is not None
            stable = (t - self._standing_since) >= self.stability
            if drop >= self.descend_enter:
                self._state = SquatState.DESCENDING
                self._descent_start = t
                self._reached_bottom = False
                self._valid_start = stable
                self._max_drop = drop
                return self._result(Feedback.DESCEND, conf)
            return self._result(Feedback.READY if stable else Feedback.STAY_STILL, conf)

        if self._state is SquatState.DESCENDING:
            self._max_drop = max(self._max_drop, drop)
            if drop >= self.bottom_enter:
                self._state = SquatState.BOTTOM
                self._reached_bottom = True
                return self._result(Feedback.DEPTH_REACHED, conf)
            if drop <= self.stand_return:
                rejected = self._max_drop >= self._meaningful
                self._enter_standing(t)
                return self._result(
                    Feedback.INCOMPLETE if rejected else Feedback.STAY_STILL,
                    conf,
                    rejected=rejected,
                )
            return self._result(Feedback.DESCEND_MORE, conf)

        if self._state is SquatState.BOTTOM:
            self._max_drop = max(self._max_drop, drop)
            if drop <= self.up_exit:
                self._state = SquatState.ASCENDING
                return self._result(Feedback.ASCEND, conf)
            return self._result(Feedback.DEPTH_REACHED, conf)

        if self._state is SquatState.ASCENDING:
            if drop >= self.bottom_enter:
                self._state = SquatState.BOTTOM
                return self._result(Feedback.DEPTH_REACHED, conf)
            if drop <= self.stand_return:
                return self._finish_rep(t, conf)
            return self._result(Feedback.EXTEND_LEGS, conf)

        self._enter_standing(t)  # pragma: no cover
        return self._result(Feedback.STAY_STILL, conf)  # pragma: no cover

    def _finish_rep(self, t: float, conf: float) -> CounterResult:
        assert self._descent_start is not None
        duration = t - self._descent_start

        feedback: str
        rejected = False
        completed = False
        if not self._reached_bottom:
            feedback, rejected = Feedback.INCOMPLETE, True
        elif duration < self.min_cycle:
            feedback, rejected = Feedback.TOO_FAST, True
        elif duration > self.max_cycle:
            feedback, rejected = Feedback.TOO_SLOW, True
        elif not self._valid_start:
            feedback, rejected = Feedback.NOT_VALID, True
        else:
            self._count += 1
            completed = True
            feedback = Feedback.VALID

        self._enter_standing(t)
        return self._result(feedback, conf, just_completed=completed, rejected=rejected)
