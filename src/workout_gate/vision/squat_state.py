"""Stati e tipi di dato della macchina a stati dello squat (puri)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SquatState(Enum):
    WAITING_FOR_BODY = "waiting_for_body"
    STANDING = "standing"
    DESCENDING = "descending"
    BOTTOM = "bottom"
    ASCENDING = "ascending"


PHASE_LABEL_IT: dict[SquatState, str] = {
    SquatState.WAITING_FOR_BODY: "In attesa del corpo",
    SquatState.STANDING: "In piedi",
    SquatState.DESCENDING: "Discesa",
    SquatState.BOTTOM: "Fondo",
    SquatState.ASCENDING: "Risalita",
}


class Feedback:
    """Messaggi dinamici (IT) mostrati sul gate."""

    BODY_NOT_VISIBLE = "Inquadra tutto il corpo"
    PARTIAL_BODY = "Corpo non completamente visibile"
    STAND_UP = "Mettiti in piedi, gambe estese"
    POSITION_DETECTED = "Posizione iniziale rilevata"
    STAY_STILL = "Rimani fermo un istante"
    READY = "Inizia lo squat"
    DESCEND = "Scendi"
    DESCEND_MORE = "Scendi ancora"
    DEPTH_REACHED = "Profondita' raggiunta"
    ASCEND = "Ora risali"
    EXTEND_LEGS = "Estendi completamente le gambe"
    VALID = "Squat valido"
    INCOMPLETE = "Movimento incompleto"
    TOO_FAST = "Movimento troppo rapido"
    TOO_SLOW = "Movimento troppo lento"
    NOT_VALID = "Ripetizione non valida"
    DONE = "Completato"


@dataclass(frozen=True)
class FrameMetrics:
    """Metriche numeriche estratte da un frame (o sintetiche nei test).

    E' l'input della macchina a stati. Non contiene immagini ne' landmark
    completi: solo numeri. Cosi' il counter e' testabile senza webcam.
    """

    timestamp: float
    body_present: bool
    knee_angle: float
    min_visibility: float
    hip_y: float = 0.0


@dataclass(frozen=True)
class CounterResult:
    state: SquatState
    rep_count: int
    just_completed: bool
    rejected: bool
    feedback: str
    confidence: float
    depth_reached: bool

    @property
    def phase_label(self) -> str:
        return PHASE_LABEL_IT[self.state]
