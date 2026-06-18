"""Entry point del pacchetto (``workout-gate`` -> ``workout_gate.main:main``)."""

from __future__ import annotations

from .cli import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
