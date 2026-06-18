"""Selezione e continuita' del soggetto principale.

MediaPipe puo' rilevare piu' persone. Questo tracker sceglie il soggetto
principale (corpo piu' grande e piu' centrale), ignora le persone piccole sullo
sfondo e mantiene la continuita': non cambia soggetto durante una ripetizione.
Se il soggetto principale sparisce per piu' di ``lost_grace_frames`` frame, segnala
``changed=True`` cosi' il counter resetta e richiede una nuova stabilizzazione.

Limite onesto (documentato): con visione monoculare la continuita' e' euristica
(prossimita' del centro fra frame), non identificazione biometrica.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """Bounding box normalizzato (0..1) di una persona rilevata."""

    cx: float
    cy: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)


@dataclass(frozen=True)
class SubjectResult:
    index: int | None
    changed: bool
    present: bool


_MAX_CENTER_DIST = math.hypot(0.5, 0.5)  # distanza max dal centro frame


class SubjectTracker:
    def __init__(
        self,
        *,
        min_area: float = 0.03,
        switch_distance: float = 0.25,
        lost_grace_frames: int = 5,
    ) -> None:
        self.min_area = min_area
        self.switch_distance = switch_distance
        self.lost_grace_frames = lost_grace_frames
        self.reset()

    def reset(self) -> None:
        self._last_center: tuple[float, float] | None = None
        self._lost = 0

    @staticmethod
    def _score(c: Candidate) -> float:
        dist = math.hypot(c.cx - 0.5, c.cy - 0.5)
        centrality = 1.0 - min(1.0, dist / _MAX_CENTER_DIST)
        return c.area * (0.5 + 0.5 * centrality)

    def select(self, candidates: list[Candidate]) -> SubjectResult:
        valid = [(i, c) for i, c in enumerate(candidates) if c.area >= self.min_area]

        if not valid:
            # Nessun soggetto valido: il corpo non e' (piu') presente.
            if self._last_center is not None:
                self._lost += 1
                if self._lost > self.lost_grace_frames:
                    self.reset()
            return SubjectResult(index=None, changed=False, present=False)

        best_idx, best_cand = max(valid, key=lambda ic: self._score(ic[1]))

        if self._last_center is None:
            # Prima acquisizione.
            self._last_center = best_cand.center
            self._lost = 0
            return SubjectResult(index=best_idx, changed=True, present=True)

        # Cerca la corrispondenza piu' vicina all'ultimo centro (continuita').
        match = min(
            valid,
            key=lambda ic: math.dist(ic[1].center, self._last_center),  # type: ignore[arg-type]
        )
        match_dist = math.dist(match[1].center, self._last_center)

        if match_dist <= self.switch_distance:
            self._last_center = match[1].center
            self._lost = 0
            return SubjectResult(index=match[0], changed=False, present=True)

        # Soggetto originale non trovato vicino: occlusione o sostituzione.
        self._lost += 1
        if self._lost > self.lost_grace_frames:
            self._last_center = best_cand.center
            self._lost = 0
            return SubjectResult(index=best_idx, changed=True, present=True)
        return SubjectResult(index=None, changed=False, present=False)
