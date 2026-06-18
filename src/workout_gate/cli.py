"""Interfaccia a riga di comando (``workout-gate ...``).

I comandi che agiscono su un'istanza in esecuzione (start/stop/pause/resume/
workout-now/reset-timer) usano il canale file-based in ``commands.py``. I comandi
standalone (run/calibrate/test-camera/doctor/stats/history/config/autostart)
girano nel processo corrente.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import commands
from .config import load_config, with_dev_interval
from .paths import config_path


def _parse_duration(text: str) -> int:
    """Converte '15m', '1h', '90s', o un numero (minuti) in secondi."""
    t = text.strip().lower()
    try:
        if t.endswith("h"):
            return int(float(t[:-1]) * 3600)
        if t.endswith("m"):
            return int(float(t[:-1]) * 60)
        if t.endswith("s"):
            return int(float(t[:-1]))
        return int(float(t) * 60)
    except ValueError as exc:
        raise SystemExit(f"Durata non valida: {text!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workout-gate",
        description="Gate del computer dietro 10 squat verificati via webcam.",
    )
    sub = p.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Avvia l'app (tray + scheduler).")
    run.add_argument(
        "--work-interval-seconds",
        type=float,
        default=None,
        help="MODALITA' SVILUPPO: intervallo workout in secondi (non persistito).",
    )

    sub.add_parser("status", help="Stato dell'istanza in esecuzione.")
    sub.add_parser("start", help="Avvia l'app in background se non e' attiva.")
    sub.add_parser("stop", help="Chiude l'istanza in esecuzione.")
    pause = sub.add_parser("pause", help="Mette in pausa (es. 15m, 1h).")
    pause.add_argument("duration", help="Durata: 15m, 30m, 1h, 90s...")
    sub.add_parser("resume", help="Riprende dalla pausa.")
    sub.add_parser("workout-now", help="Apre subito il gate.")
    sub.add_parser("calibrate", help="Calibrazione webcam interattiva.")
    sub.add_parser("test-camera", help="Test webcam con scheletro (prova inquadratura).")
    sub.add_parser("stats", help="Statistiche.")
    sub.add_parser("history", help="Storico sessioni recenti.")
    sub.add_parser("config", help="Mostra la configurazione effettiva.")
    sub.add_parser("doctor", help="Diagnostica ambiente.")
    sub.add_parser("install-autostart", help="Installa l'avvio automatico al login.")
    sub.add_parser("remove-autostart", help="Rimuove l'avvio automatico.")
    rt = sub.add_parser("reset-timer", help="Azzera il tempo attivo accumulato.")
    rt.add_argument("--yes", action="store_true", help="Salta la conferma.")
    return p


def _require_running() -> bool:
    if not commands.is_running():
        print("Workout Gate non risulta in esecuzione. Avvialo con: workout-gate run")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "run"

    if command == "run":
        return _cmd_run(args)
    if command == "status":
        return _cmd_status()
    if command == "start":
        return _cmd_start()
    if command == "stop":
        if _require_running():
            commands.send_command("quit")
            print("Chiusura richiesta.")
        return 0
    if command == "pause":
        if not _require_running():
            return 1
        commands.send_command("pause", seconds=_parse_duration(args.duration))
        print(f"In pausa per {args.duration}.")
        return 0
    if command == "resume":
        if not _require_running():
            return 1
        commands.send_command("resume")
        print("Ripreso.")
        return 0
    if command == "workout-now":
        if not _require_running():
            return 1
        commands.send_command("workout_now")
        print("Workout richiesto.")
        return 0
    if command == "calibrate":
        return _cmd_calibrate()
    if command == "test-camera":
        return _cmd_test_camera()
    if command == "stats":
        return _cmd_stats()
    if command == "history":
        return _cmd_history()
    if command == "config":
        return _cmd_config()
    if command == "doctor":
        from .diagnostics import doctor

        return doctor()
    if command == "install-autostart":
        from . import autostart

        print(f"Autostart installato: {autostart.install()}")
        return 0
    if command == "remove-autostart":
        from . import autostart

        print("Autostart rimosso." if autostart.remove() else "Autostart non presente.")
        return 0
    if command == "reset-timer":
        return _cmd_reset_timer(args)
    return 0


def _cmd_run(args) -> int:
    from .logging_config import setup_logging

    setup_logging(level=logging.INFO)
    cfg = load_config(config_path())
    if getattr(args, "work_interval_seconds", None) is not None:
        cfg = with_dev_interval(cfg, args.work_interval_seconds)

    from .paths import lock_path
    from .single_instance import AlreadyRunning, SingleInstance

    try:
        instance = SingleInstance(lock_path()).acquire()
    except AlreadyRunning:
        print("Workout Gate e' gia' in esecuzione.")
        return 1

    try:
        from .app import WorkoutGateApp

        return WorkoutGateApp(cfg).run()
    finally:
        instance.release()


def _cmd_status() -> int:
    st = commands.read_status()
    if not st or not commands.is_running():
        print("Non in esecuzione.")
        return 1
    print(f"Stato: {st.get('state')}")
    print(f"Gate attivo: {st.get('gate_active')}")
    print(f"Tempo attivo accumulato: {st.get('accumulated_seconds')}s")
    print(f"Mancano: {st.get('remaining_seconds')}s di uso attivo")
    print(f"In pausa: {st.get('paused')}")
    return 0


def _cmd_start() -> int:
    import subprocess

    if commands.is_running():
        print("Gia' in esecuzione.")
        return 0
    exe = sys.executable
    pythonw = exe.replace("python.exe", "pythonw.exe")
    subprocess.Popen([pythonw, "-m", "workout_gate", "run"])
    print("Avviato in background.")
    return 0


def _cmd_calibrate() -> int:
    from .vision.preview import calibrate_interactive

    cfg = load_config(config_path())
    return calibrate_interactive(cfg, config_path())


def _cmd_test_camera() -> int:
    from .vision.preview import live_preview

    cfg = load_config(config_path())
    return live_preview(cfg)


def _cmd_stats() -> int:
    from .paths import state_path
    from .storage import JsonStore

    s = JsonStore(state_path()).load()
    print("Workout Gate - statistiche")
    print(f"  Workout completati: {s.get('workouts_completed', 0)}")
    print(f"  Squat totali:       {s.get('total_squats', 0)}")
    print(f"  Streak attuale:     {s.get('streak_current', 0)}")
    print(f"  Streak piu' lungo:  {s.get('streak_longest', 0)}")
    print(f"  Record ripetizioni: {s.get('personal_record_reps', 0)}")
    print(f"  Bypass:             {s.get('bypasses', 0)}")
    print(f"  Errori tecnici:     {s.get('technical_errors', 0)}")
    return 0


def _cmd_history() -> int:
    from .paths import state_path
    from .storage import JsonStore

    sessions = JsonStore(state_path()).load().get("sessions", [])
    if not sessions:
        print("Nessuna sessione registrata.")
        return 0
    print("Storico recente:")
    for s in sessions[-20:]:
        print(f"  {s.get('ts')}  {s.get('outcome')}  reps={s.get('reps')}")
    return 0


def _cmd_config() -> int:
    cfg = load_config(config_path())
    print(f"File config: {config_path()}")
    print(f"  Intervallo lavoro:  {cfg.timer.work_interval_minutes} min")
    print(f"  Soglia idle:        {cfg.timer.idle_threshold_seconds} s")
    print(f"  Ripetizioni:        {cfg.workout.required_repetitions}")
    print(f"  Eretto / fondo:     {cfg.vision.standing_knee_angle_degrees} / "
          f"{cfg.vision.bottom_knee_angle_degrees} gradi")
    print("  Privacy: video/frame/immagini/rete/telemetria/analytics = OFF (forzati)")
    return 0


def _cmd_reset_timer(args) -> int:
    if not args.yes:
        reply = input("Azzerare il tempo attivo accumulato? [y/N] ").strip().lower()
        if reply not in {"y", "yes", "s", "si"}:
            print("Annullato.")
            return 1
    if commands.is_running():
        commands.send_command("reset_timer")
        print("Reset inviato all'istanza in esecuzione.")
    else:
        from .paths import state_path
        from .storage import JsonStore

        JsonStore(state_path()).update(accumulated_active_seconds=0.0)
        print("Tempo attivo azzerato.")
    return 0
