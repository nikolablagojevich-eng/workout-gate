"""Disegno dell'overlay (scheletro, angolo, fase, contatore) sul frame.

Usa OpenCV (import lazy). Il frame annotato e' solo per la visualizzazione live
(self-view): non viene mai salvato. Le coordinate dei landmark sono normalizzate
(0..1); il mirroring riflette anche le x.
"""

from __future__ import annotations

from .pose_detector import (
    L_ANKLE,
    L_HIP,
    L_KNEE,
    L_SHOULDER,
    R_ANKLE,
    R_HIP,
    R_KNEE,
    R_SHOULDER,
)

# Connessioni minime per uno scheletro leggibile su gambe e tronco.
_CONNECTIONS = [
    (L_SHOULDER, R_SHOULDER),
    (L_SHOULDER, L_HIP),
    (R_SHOULDER, R_HIP),
    (L_HIP, R_HIP),
    (L_HIP, L_KNEE),
    (L_KNEE, L_ANKLE),
    (R_HIP, R_KNEE),
    (R_KNEE, R_ANKLE),
]
_KEY_POINTS = [L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]


def annotate(frame, observation, counter_result, *, mirror: bool = True):
    import cv2

    img = cv2.flip(frame, 1) if mirror else frame
    h, w = img.shape[:2]
    lms = getattr(observation, "landmarks", None) or []

    def px(i: int) -> tuple[int, int]:
        x, y, _ = lms[i]
        if mirror:
            x = 1.0 - x
        return int(x * w), int(y * h)

    def visible(i: int) -> bool:
        return i < len(lms) and lms[i][2] >= 0.5

    if lms:
        for a, b in _CONNECTIONS:
            if visible(a) and visible(b):
                cv2.line(img, px(a), px(b), (0, 220, 120), 2)
        for i in _KEY_POINTS:
            if visible(i):
                cv2.circle(img, px(i), 5, (40, 200, 255), -1)
        if visible(L_KNEE) or visible(R_KNEE):
            kp = px(L_KNEE) if visible(L_KNEE) else px(R_KNEE)
            cv2.putText(
                img,
                f"{counter_result.confidence * 100:.0f}%",
                (kp[0] + 8, kp[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    banner = f"{counter_result.phase_label}"
    cv2.putText(
        img, banner, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA
    )
    return img
