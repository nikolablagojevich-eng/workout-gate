"""Geometria articolare pura: angoli da coordinate di landmark.

Nessuna dipendenza esterna oltre la stdlib. Le coordinate sono sequenze
``(x, y)`` (eventuali componenti aggiuntive vengono ignorate). Le unita' di x/y
sono irrilevanti: gli angoli sono invarianti per scala e traslazione.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = Sequence[float]


def angle_at(a: Point, b: Point, c: Point) -> float:
    """Angolo interno (in gradi) nel vertice ``b`` formato dai segmenti b->a e b->c.

    Ritorna un valore in ``[0, 180]``. Se uno dei due segmenti ha lunghezza
    nulla (landmark coincidenti) l'angolo non e' definito: si ritorna ``180.0``
    (gamba considerata estesa, scelta conservativa: non innesca una discesa).
    """
    bax, bay = a[0] - b[0], a[1] - b[1]
    bcx, bcy = c[0] - b[0], c[1] - b[1]
    na = math.hypot(bax, bay)
    nc = math.hypot(bcx, bcy)
    if na == 0.0 or nc == 0.0:
        return 180.0
    cos_ang = (bax * bcx + bay * bcy) / (na * nc)
    cos_ang = max(-1.0, min(1.0, cos_ang))
    return math.degrees(math.acos(cos_ang))


def midpoint(a: Point, b: Point) -> tuple[float, float]:
    """Punto medio fra due landmark (solo componenti x, y)."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def vertical_position(point: Point) -> float:
    """Coordinata verticale di un landmark.

    Convenzione immagine: y cresce verso il basso. Valori piccoli = in alto.
    """
    return point[1]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
