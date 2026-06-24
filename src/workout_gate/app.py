"""Orchestratore principale: scheduler + tray + gate + persistenza.

Tiene la memoria del task. Un QTimer a 1 Hz fa avanzare lo scheduler con lo stato
del sistema (lock, idle), drena i comandi della CLI, persiste periodicamente e
aggiorna tray e file di stato. Quando lo scheduler segnala il gate dovuto, apre il
GateController; al termine traduce l'esito in azione (reset / bypass / retry).
"""

from __future__ import annotations

import datetime
import logging
import subprocess
import sys
import time
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import commands
from .config import AppConfig
from .gate.controller import (
    OUTCOME_BYPASS,
    OUTCOME_COMPLETED,
    OUTCOME_SKIPPED,
    GateController,
)
from .idle_detector import IdleDetector
from .paths import config_path, state_path
from .scheduler import Scheduler, SchedulerState
from .storage import JsonStore
from .tray import Tray, TrayCallbacks
from .ui.desktop_widget import DesktopWidget
from .ui.settings_window import SettingsWindow
from .ui.stats_window import StatsWindow
from .windows_session import SessionMonitor

logger = logging.getLogger(__name__)


def _fmt_mmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class WorkoutGateApp:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
        self.app.setQuitOnLastWindowClosed(False)

        self.store = JsonStore(state_path())
        state = self.store.load()

        self.scheduler = Scheduler(
            work_interval_seconds=cfg.effective_work_interval_seconds,
            idle_threshold_seconds=cfg.timer.idle_threshold_seconds,
            on_gate_due=self._open_gate,
            max_tick_gap_seconds=cfg.timer.max_tick_gap_seconds,
            initial_accumulated=float(state.get("accumulated_active_seconds", 0.0)),
            retry_after_error_seconds=cfg.timer.retry_after_technical_error_minutes * 60,
            interval_after_bypass_seconds=cfg.timer.interval_after_emergency_bypass_minutes * 60,
        )
        self.idle = IdleDetector(cfg.timer.idle_threshold_seconds)
        self.session = SessionMonitor()

        self.controller: GateController | None = None
        self._gate_active = False
        self._last_persist = 0.0
        self._dialogs: list[object] = []

        self.tray = Tray(
            TrayCallbacks(
                workout_now=self._cmd_workout_now,
                pause_minutes=self._cmd_pause_minutes,
                pause_until_login=self._cmd_pause_until_login,
                resume=self._cmd_resume,
                settings=self._show_settings,
                stats=self._show_stats,
                calibrate=lambda: self._spawn("calibrate"),
                test_camera=lambda: self._spawn("test-camera"),
                doctor=self._show_doctor,
                toggle_widget=self._toggle_widget,
                quit=self.quit,
            )
        )

        self.widget = DesktopWidget()
        self.widget.turnedOn.connect(self._widget_on)
        self.widget.turnedOff.connect(self._widget_off)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ----- ciclo di vita -----
    def run(self) -> int:
        if self.cfg.dev_work_interval_seconds is not None:
            logger.warning(
                "MODALITA' SVILUPPO: intervallo workout = %.0fs",
                self.cfg.dev_work_interval_seconds,
            )
        # Scarta comandi rimasti nel canale da prima dell'avvio (no stato spurio).
        commands.drain_commands()
        self.tray.show()
        if self.cfg.startup.show_widget:
            self.widget.show()
            self.widget.place_bottom_right()
            if not self.cfg.startup.widget_on_top:
                self.widget.pin_to_desktop()
                self.widget.place_bottom_right()
        self._tick()
        self._timer.start()
        logger.info("Workout Gate avviato.")
        return self.app.exec()

    def quit(self) -> None:
        self._persist()
        self._timer.stop()
        self.widget.hide()
        self.tray.hide()
        self.app.quit()

    # ----- tick principale -----
    def _tick(self) -> None:
        now = time.monotonic()
        for cmd in commands.drain_commands():
            self._handle_external_command(cmd)

        if not self._gate_active:
            locked = self.session.is_locked()
            idle = self.idle.idle_seconds()
            self.scheduler.tick(now, locked=locked, idle_seconds=idle)

        if now - self._last_persist >= self.cfg.timer.persistence_interval_seconds:
            self._persist()
            self._last_persist = now

        self._update_status()

    def _persist(self) -> None:
        try:
            self.store.update(
                accumulated_active_seconds=self.scheduler.accumulated_seconds,
                last_persisted_iso=_now_iso(),
            )
        except OSError:
            logger.exception("Persistenza fallita (ignorata).")

    def _update_status(self) -> None:
        if self._gate_active:
            self.tray.set_status("Workout in corso")
            self.widget.set_state(enabled=True, status="in corso")
        elif self.scheduler.state is SchedulerState.PAUSED:
            self.tray.set_status("In pausa", paused=True)
            self.widget.set_state(enabled=False, status="spento")
        else:
            rem = _fmt_mmss(self.scheduler.remaining_seconds)
            self.tray.set_status(f"Prossimo workout: {rem} di uso attivo")
            self.widget.set_state(enabled=True, status=f"tra {rem}")

        try:
            commands.write_status(
                {
                    "state": self.scheduler.state.value,
                    "gate_active": self._gate_active,
                    "remaining_seconds": round(self.scheduler.remaining_seconds, 1),
                    "accumulated_seconds": round(self.scheduler.accumulated_seconds, 1),
                    "paused": self.scheduler.is_paused,
                }
            )
        except OSError:
            pass

    # ----- gate -----
    def _open_gate(self) -> None:
        if self._gate_active:
            return
        self._gate_active = True
        logger.info("Apertura Workout Gate.")
        self.controller = GateController(self.cfg)
        self.controller.finished.connect(self._on_gate_finished)
        try:
            self.controller.start()
        except Exception as exc:  # noqa: BLE001 - fail-open
            logger.exception("Avvio gate fallito")
            self._on_gate_finished("error", str(exc))

    def _on_gate_finished(self, outcome: str, payload) -> None:
        self._gate_active = False
        self.controller = None
        if outcome == OUTCOME_COMPLETED:
            self.scheduler.on_workout_completed()
            self._record_completion()
        elif outcome == OUTCOME_BYPASS:
            self.scheduler.on_emergency_bypass()
            self._record_bypass(str(payload) if payload else "altro")
        elif outcome == OUTCOME_SKIPPED:
            # OFF dal widget: nessun debito, nessuna statistica. Lo scheduler resta
            # in pausa (spento) finche' non si riaccende con ON.
            self.scheduler.on_workout_completed()
            self.scheduler.pause_until_login()
        else:
            self.scheduler.on_technical_error()
            self._record_error(str(payload))
        self._persist()
        self._update_status()

    # ----- statistiche -----
    def _record_completion(self) -> None:
        data = self.store.load()
        today = datetime.date.today()
        last = data.get("last_workout_date")
        if last == today.isoformat():
            pass
        elif last == (today - datetime.timedelta(days=1)).isoformat():
            data["streak_current"] = int(data.get("streak_current", 0)) + 1
        else:
            data["streak_current"] = 1
        data["streak_longest"] = max(int(data.get("streak_longest", 0)), data["streak_current"])
        data["workouts_completed"] = int(data.get("workouts_completed", 0)) + 1
        reps = self.cfg.workout.required_repetitions
        data["total_squats"] = int(data.get("total_squats", 0)) + reps
        data["personal_record_reps"] = max(
            int(data.get("personal_record_reps", 0)), self.cfg.workout.required_repetitions
        )
        data["last_workout_date"] = today.isoformat()
        data["last_workout_iso"] = _now_iso()
        self._append_session(data, "completed", self.cfg.workout.required_repetitions)
        self.store.save(data)

    def _record_bypass(self, category: str) -> None:
        data = self.store.load()
        data["bypasses"] = int(data.get("bypasses", 0)) + 1
        self._append_session(data, f"bypass:{category}", 0)
        self.store.save(data)

    def _record_error(self, message: str) -> None:
        data = self.store.load()
        data["technical_errors"] = int(data.get("technical_errors", 0)) + 1
        self._append_session(data, "error", 0)
        self.store.save(data)

    @staticmethod
    def _append_session(data: dict, outcome: str, reps: int) -> None:
        sessions = data.get("sessions", [])
        sessions.append({"ts": _now_iso(), "outcome": outcome, "reps": reps})
        data["sessions"] = sessions[-50:]

    # ----- comandi (tray / CLI) -----
    def _cmd_workout_now(self) -> None:
        self.scheduler.workout_now()

    def _cmd_pause_minutes(self, minutes: int) -> None:
        self.scheduler.pause(time.monotonic(), minutes * 60)
        self._update_status()

    def _cmd_pause_until_login(self) -> None:
        self.scheduler.pause_until_login()
        self._update_status()

    def _cmd_resume(self) -> None:
        self.scheduler.resume()
        self._update_status()

    # ----- widget desktop ON/OFF -----
    def _widget_on(self) -> None:
        """ON: riaccende il counter."""
        self.scheduler.resume()
        self._update_status()

    def _widget_off(self) -> None:
        """OFF: spegne il counter (pausa indefinita) e chiude un eventuale gate
        gia' aperto senza debito. Per riunioni/presentazioni."""
        self.scheduler.pause_until_login()
        if self._gate_active and self.controller is not None:
            self.controller.cancel()
        self._update_status()

    def _toggle_widget(self) -> None:
        if self.widget.isVisible():
            self.widget.hide()
        else:
            self.widget.show()
            self.widget.place_bottom_right()
            if not self.cfg.startup.widget_on_top:
                self.widget.pin_to_desktop()
                self.widget.place_bottom_right()

    def _handle_external_command(self, cmd: dict) -> None:
        action = cmd.get("action")
        if action == "workout_now":
            self._cmd_workout_now()
        elif action == "pause":
            self.scheduler.pause(time.monotonic(), float(cmd.get("seconds", 900)))
        elif action == "pause_until_login":
            self._cmd_pause_until_login()
        elif action == "resume":
            self._cmd_resume()
        elif action == "reset_timer":
            self.scheduler.reset_timer()
            self._persist()
        elif action == "quit":
            self.quit()

    # ----- finestre -----
    def _show_settings(self) -> None:
        win = SettingsWindow(self.cfg, config_path())
        win.show()
        self._dialogs.append(win)

    def _show_stats(self) -> None:
        win = StatsWindow(self.store.load())
        win.show()
        self._dialogs.append(win)

    def _show_doctor(self) -> None:
        from .diagnostics import run_checks

        lines = [
            f"[{'OK' if c.ok else '!!'}] {c.name}: {c.detail}"
            for c in run_checks(include_camera=not self._gate_active)
        ]
        QMessageBox.information(None, "Workout Gate - Diagnostica", "\n".join(lines))

    def _spawn(self, subcommand: str) -> None:
        try:
            subprocess.Popen([sys.executable, "-m", "workout_gate", subcommand])
        except OSError:
            logger.exception("Impossibile avviare il sottocomando %s", subcommand)
