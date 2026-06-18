"""Prova dal vivo: webcam -> MediaPipe -> counter, con traccia del movimento.

Cattura N secondi di frame veri e stampa una riga ogni ~0.4s (angolo ginocchio,
visibilita', fase, contatore) piu' un riepilogo. Non apre il gate, non salva nulla.

Uso: python scripts/probe_pipeline.py [secondi]
"""

from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from workout_gate.config import load_config  # noqa: E402
from workout_gate.gate.engine import create_engine  # noqa: E402
from workout_gate.paths import config_path  # noqa: E402


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    cfg = load_config(config_path())
    engine = create_engine(cfg)

    total = 0
    present = 0
    sh_ys: list[float] = []
    last_print = 0.0
    last_count = 0

    print(f"Cattura {duration:.0f}s ({cfg.vision.exercise_mode}). Fai 3-4 squat lenti.\n")
    try:
        t0 = time.monotonic()
        while True:
            now = time.monotonic()
            elapsed = now - t0
            if elapsed >= duration:
                break
            step = engine.step(now)
            total += 1
            obs = step.observation
            if step.subject_present:
                present += 1
                sh_ys.append(obs.shoulder_y)

            if step.counter.rejected:
                print(f"  ... scartato: {step.counter.feedback}")

            if step.count != last_count or (elapsed - last_print) >= 0.4:
                last_print = elapsed
                if step.count != last_count:
                    print(f"  >>> SQUAT VALIDO! totale = {step.count}")
                    last_count = step.count
                sy = f"{obs.shoulder_y:0.2f}" if step.subject_present else "----"
                base = getattr(engine.counter, "baseline", None)
                bs = f"{base:0.2f}" if base is not None else "----"
                body = "corpo" if step.subject_present else "no-corpo"
                print(
                    f"  t={elapsed:4.1f}s  spalle_y={sy}  base={bs}  "
                    f"{body:8s}  fase={step.counter.phase_label:14s}  count={step.count}"
                )
            time.sleep(0.02)
    finally:
        engine.close()

    print("\n--- riepilogo ---")
    print(f"frame elaborati:          {total}")
    print(f"frame con corpo rilevato: {present} ({100 * present / max(1, total):.0f}%)")
    if sh_ys:
        print(f"spalle_y:                 min {min(sh_ys):.2f} / max {max(sh_ys):.2f}")
        print(f"escursione verticale:     {max(sh_ys) - min(sh_ys):.2f}")
    print(f"SQUAT CONTATI:            {engine.counter.count}")
    print("webcam rilasciata, nessun frame salvato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
