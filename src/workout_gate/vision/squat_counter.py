"""Macchina a stati esplicita per il conteggio degli squat.

Ciclo valido: STANDING -> DESCENDING -> BOTTOM -> ASCENDING -> STANDING.
Una ripetizione e' conteggiata UNA sola volta, alla chiusura del ciclo, e solo se:

* il corpo era visibile per tutto il movimento;
* la posizione eretta iniziale era stabile (>= standing_stability_seconds);
* e' stata raggiunta la profondita' (BOTTOM, ginocchio <= bottom_angle);
* la gamba e' tornata estesa (>= standing - hysteresis);
* la durata del ciclo e' realistica (min..max).

Isteresi e debounce impediscono il doppio conteggio e i conteggi da oscillazione
vicino alle soglie. Se il soggetto sparisce o i landmark scendono sotto la
visibilita' minima, la macchina torna in WAITING_FOR_BODY e richiede una nuova
stabilizzazione prima di riprendere.
"""

from __future__ import annotations

from .squat_state import CounterResult, Feedback, FrameMetrics, SquatState


class SquatCounter:
    def __init__(
        self,
        *,
        standing_knee_angle: float = 160.0,
        bottom_knee_angle: float = 100.0,
        hysteresis: float = 8.0,
        min_visibility: float = 0.65,
        standing_stability_seconds: float = 0.4,
        min_cycle_seconds: float = 0.8,
        max_cycle_seconds: float = 8.0,
    ) -> None:
        self.standing = standing_knee_angle
        self.bottom = bottom_knee_angle
        self.h = hysteresis
        self.min_visibility = min_visibility
        self.stability = standing_stability_seconds
        self.min_cycle = min_cycle_seconds
        self.max_cycle = max_cycle_seconds

        # Soglie con isteresi (precalcolate).
        self.down_enter = self.standing - self.h   # sotto -> inizia discesa
        self.bottom_enter = self.bottom            # sotto -> fondo raggiunto
        self.up_exit = self.bottom + self.h        # sopra dopo fondo -> risalita
        self.stand_return = self.standing - self.h  # sopra dopo risalita -> eretto
        # Soglia "tentativo serio" per distinguere un mezzo-squat da un micro-wobble.
        self._meaningful_attempt = (self.standing + self.bottom) / 2.0

        self.reset_all()

    # ----- stato interno -----
    def reset_all(self) -> None:
        self._state = SquatState.WAITING_FOR_BODY
        self._count = 0
        self._standing_since: float | None = None
        self._reset_rep()

    def _reset_rep(self) -> None:
        self._descent_start_t: float | None = None
        self._reached_bottom = False
        self._valid_start = False
        self._min_angle = 180.0

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

    # ----- aggiornamento per-frame -----
    def update(self, m: FrameMetrics) -> CounterResult:
        conf = m.min_visibility

        # 1) Gate di presenza/visibilita'. Reset duro: nuova stabilizzazione.
        if not m.body_present or m.min_visibility < self.min_visibility:
            if self._state is not SquatState.WAITING_FOR_BODY:
                self._state = SquatState.WAITING_FOR_BODY
                self._standing_since = None
                self._reset_rep()
            msg = Feedback.BODY_NOT_VISIBLE if not m.body_present else Feedback.PARTIAL_BODY
            return self._result(msg, conf)

        angle = m.knee_angle
        t = m.timestamp

        if self._state is SquatState.WAITING_FOR_BODY:
            if angle >= self.stand_return:
                self._enter_standing(t)
                return self._result(Feedback.POSITION_DETECTED, conf)
            return self._result(Feedback.STAND_UP, conf)

        if self._state is SquatState.STANDING:
            assert self._standing_since is not None
            stable = (t - self._standing_since) >= self.stability
            if angle < self.down_enter:
                self._state = SquatState.DESCENDING
                self._descent_start_t = t
                self._reached_bottom = False
                self._valid_start = stable
                self._min_angle = angle
                return self._result(Feedback.DESCEND, conf)
            return self._result(Feedback.READY if stable else Feedback.STAY_STILL, conf)

        if self._state is SquatState.DESCENDING:
            self._min_angle = min(self._min_angle, angle)
            if angle <= self.bottom_enter:
                self._state = SquatState.BOTTOM
                self._reached_bottom = True
                return self._result(Feedback.DEPTH_REACHED, conf)
            if angle >= self.stand_return:
                # Risalita senza aver toccato il fondo: mezzo squat -> scartato.
                rejected = self._min_angle <= self._meaningful_attempt
                self._enter_standing(t)
                return self._result(
                    Feedback.INCOMPLETE if rejected else Feedback.STAY_STILL,
                    conf,
                    rejected=rejected,
                )
            return self._result(Feedback.DESCEND_MORE, conf)

        if self._state is SquatState.BOTTOM:
            self._min_angle = min(self._min_angle, angle)
            if angle >= self.up_exit:
                self._state = SquatState.ASCENDING
                return self._result(Feedback.ASCEND, conf)
            return self._result(Feedback.DEPTH_REACHED, conf)

        if self._state is SquatState.ASCENDING:
            if angle <= self.bottom_enter:
                # Rimbalzo al fondo: resta la stessa ripetizione, non si conta.
                self._state = SquatState.BOTTOM
                return self._result(Feedback.DEPTH_REACHED, conf)
            if angle >= self.stand_return:
                return self._finish_rep(t, conf)
            return self._result(Feedback.EXTEND_LEGS, conf)

        # Difensivo: stato sconosciuto.
        self._enter_standing(t)  # pragma: no cover
        return self._result(Feedback.STAY_STILL, conf)  # pragma: no cover

    def _finish_rep(self, t: float, conf: float) -> CounterResult:
        assert self._descent_start_t is not None
        duration = t - self._descent_start_t

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
        return self._result(
            feedback, conf, just_completed=completed, rejected=rejected
        )
