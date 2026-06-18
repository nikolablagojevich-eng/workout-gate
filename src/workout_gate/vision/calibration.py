"""Calibrazione delle soglie a partire da qualche secondo di movimento.

Logica pura e testabile: accumula gli angoli del ginocchio mentre l'utente sta
in piedi e fa uno squat, poi deriva la soglia di posizione eretta e quella di
profondita'. Si salvano SOLO numeri (gli angoli sono metriche, non immagini).
"""

from __future__ import annotations

from dataclasses import dataclass


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[k]


@dataclass
class CalibrationResult:
    standing_knee_angle_degrees: float
    bottom_knee_angle_degrees: float
    samples: int


class CalibrationAccumulator:
    def __init__(self, min_visibility: float = 0.65) -> None:
        self.min_visibility = min_visibility
        self._angles: list[float] = []

    def add(self, knee_angle: float, min_visibility: float, *, present: bool = True) -> None:
        if present and min_visibility >= self.min_visibility:
            self._angles.append(knee_angle)

    @property
    def samples(self) -> int:
        return len(self._angles)

    @property
    def observed_range(self) -> float:
        if not self._angles:
            return 0.0
        return _percentile(self._angles, 90) - _percentile(self._angles, 5)

    def has_enough_range(self, *, min_samples: int = 30, min_range: float = 35.0) -> bool:
        return self.samples >= min_samples and self.observed_range >= min_range

    def result(self) -> CalibrationResult:
        """Deriva le soglie. Posizione eretta = p90; fondo = vicino al minimo osservato."""
        standing = _percentile(self._angles, 90)
        deepest = _percentile(self._angles, 5)
        # Soglia eretta leggermente sotto il p90 per tolleranza.
        standing_threshold = max(150.0, min(178.0, standing - 3.0))
        # Soglia fondo: richiede di avvicinarsi alla profondita' osservata, con margine.
        bottom_threshold = deepest + 0.25 * (standing - deepest)
        bottom_threshold = max(70.0, min(standing_threshold - 30.0, bottom_threshold))
        return CalibrationResult(
            standing_knee_angle_degrees=round(standing_threshold, 1),
            bottom_knee_angle_degrees=round(bottom_threshold, 1),
            samples=self.samples,
        )
