"""Test del widget desktop ON/OFF (offscreen). Richiede PySide6 (venv 3.12)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from workout_gate.ui.desktop_widget import DesktopWidget  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_buttons_emit_signals():
    _app()
    w = DesktopWidget()
    fired = {"on": 0, "off": 0}
    w.turnedOn.connect(lambda: fired.__setitem__("on", fired["on"] + 1))
    w.turnedOff.connect(lambda: fired.__setitem__("off", fired["off"] + 1))
    w._on.click()
    w._off.click()
    assert fired["on"] == 1
    assert fired["off"] == 1


def test_set_state_toggles_lit():
    _app()
    w = DesktopWidget()
    w.set_state(enabled=True, status="tra 12:00")
    assert w._on.property("lit") == "true"
    assert w._off.property("lit") == "false"

    w.set_state(enabled=False, status="spento")
    assert w._on.property("lit") == "false"
    assert w._off.property("lit") == "true"
    assert w._status.text() == "spento"
