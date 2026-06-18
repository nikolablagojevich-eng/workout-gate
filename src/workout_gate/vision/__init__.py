"""Computer vision: geometria, macchina a stati squat, subject tracker.

`geometry`, `squat_state`, `squat_counter`, `subject_tracker` sono puri (solo
math, niente dipendenze pesanti) e quindi testabili senza webcam.
`camera`, `pose_detector`, `calibration` importano OpenCV/MediaPipe in modo lazy.
"""
