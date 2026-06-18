"""Workout Gate — gate del computer dietro squat verificati via webcam.

Pacchetto v1. Il core logico (timer active-time, geometria, macchina a stati
dello squat, subject tracker, storage, single instance) non importa MediaPipe,
OpenCV o PySide6 al livello di modulo: e' testabile senza webcam e senza GUI.
Il layer visione/UI usa import lazy.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
