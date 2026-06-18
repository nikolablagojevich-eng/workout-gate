"""Configurazione tipizzata e validata.

Caricamento da YAML con default sicuri. I valori privacy sono **forzati** nel
codice: qualunque tentativo di abilitarli da file viene ignorato e loggato.
La validazione e' rigorosa: una config incoerente solleva ``ConfigError``
(che il chiamante tratta come errore tecnico -> fail-open).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class ConfigError(ValueError):
    """Configurazione non valida o incoerente."""


@dataclass(frozen=True)
class TimerConfig:
    work_interval_minutes: float = 30.0
    idle_threshold_seconds: float = 120.0
    persistence_interval_seconds: float = 15.0
    retry_after_technical_error_minutes: float = 10.0
    interval_after_emergency_bypass_minutes: float = 10.0
    # Gap massimo (s) fra due tick oltre il quale il tempo NON viene conteggiato
    # (sleep, ibernazione, processo sospeso). Protegge il timer active-time.
    max_tick_gap_seconds: float = 5.0

    @property
    def work_interval_seconds(self) -> float:
        return self.work_interval_minutes * 60.0


@dataclass(frozen=True)
class WorkoutConfig:
    exercise: str = "squat"
    required_repetitions: int = 10
    minimum_cycle_duration_seconds: float = 0.8
    maximum_cycle_duration_seconds: float = 8.0
    completion_message_seconds: float = 1.0


@dataclass(frozen=True)
class VisionConfig:
    camera_index: int = 0
    min_landmark_visibility: float = 0.65
    standing_knee_angle_degrees: float = 160.0
    bottom_knee_angle_degrees: float = 100.0
    standing_stability_seconds: float = 0.4
    threshold_hysteresis_degrees: float = 8.0
    mirror_preview: bool = True
    calibration_required: bool = True
    # Modalita' di rilevamento:
    #  - "torso": conta lo squat dal movimento verticale del busto (spalle).
    #    Funziona con una webcam che inquadra solo testa e spalle (laptop).
    #  - "knee": angolo del ginocchio (richiede gambe interamente in quadro).
    exercise_mode: str = "torso"
    # Modalita' torso: calo verticale minimo delle spalle (frazione di frame, 0..1)
    # per considerare la discesa abbastanza profonda. Va dimensionato sull'ampiezza
    # reale del movimento: piu' grande se si e' vicini alla webcam (squat "grande"
    # nel frame). 0.20 e' un buon default per una postazione da laptop.
    torso_min_drop: float = 0.20
    # Visibilita' minima delle spalle in modalita' torso (di norma ~1.0).
    torso_min_visibility: float = 0.6


@dataclass(frozen=True)
class PrivacyConfig:
    """Valori privacy FORZATI. Non modificabili da file o UI."""

    save_video: bool = False
    save_frames: bool = False
    save_images: bool = False
    network_access: bool = False
    telemetry: bool = False
    analytics: bool = False


@dataclass(frozen=True)
class StartupConfig:
    start_at_login: bool = True
    start_minimized_to_tray: bool = True


@dataclass(frozen=True)
class SafetyConfig:
    emergency_bypass_hold_seconds: float = 10.0
    technical_fail_open: bool = True


@dataclass(frozen=True)
class AppConfig:
    schema_version: int = SCHEMA_VERSION
    enabled: bool = True
    timer: TimerConfig = field(default_factory=TimerConfig)
    workout: WorkoutConfig = field(default_factory=WorkoutConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    startup: StartupConfig = field(default_factory=StartupConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    # Override runtime (modalita' sviluppo). Non viene mai persistito.
    dev_work_interval_seconds: float | None = None

    @property
    def effective_work_interval_seconds(self) -> float:
        if self.dev_work_interval_seconds is not None:
            return self.dev_work_interval_seconds
        return self.timer.work_interval_seconds


def _positive(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{name} deve essere > 0 (valore: {value!r})")


def validate(cfg: AppConfig) -> None:
    """Solleva ConfigError se la config e' incoerente."""
    _positive("timer.work_interval_minutes", cfg.timer.work_interval_minutes)
    _positive("timer.idle_threshold_seconds", cfg.timer.idle_threshold_seconds)
    _positive("timer.persistence_interval_seconds", cfg.timer.persistence_interval_seconds)
    _positive("timer.max_tick_gap_seconds", cfg.timer.max_tick_gap_seconds)

    if cfg.workout.exercise != "squat":
        raise ConfigError("workout.exercise: in v1 e' supportato solo 'squat'")
    if cfg.workout.required_repetitions < 1:
        raise ConfigError("workout.required_repetitions deve essere >= 1")

    mn = cfg.workout.minimum_cycle_duration_seconds
    mx = cfg.workout.maximum_cycle_duration_seconds
    _positive("workout.minimum_cycle_duration_seconds", mn)
    if mx <= mn:
        raise ConfigError("maximum_cycle_duration_seconds deve essere > minimum")

    v = cfg.vision
    if v.exercise_mode not in {"torso", "knee"}:
        raise ConfigError("vision.exercise_mode deve essere 'torso' o 'knee'")
    if not (0.0 < v.torso_min_drop < 1.0):
        raise ConfigError("vision.torso_min_drop deve stare in (0, 1)")
    if not (0.0 < v.torso_min_visibility <= 1.0):
        raise ConfigError("vision.torso_min_visibility deve stare in (0, 1]")
    if not (0.0 < v.min_landmark_visibility <= 1.0):
        raise ConfigError("vision.min_landmark_visibility deve stare in (0, 1]")
    if not (0.0 < v.bottom_knee_angle_degrees < v.standing_knee_angle_degrees <= 180.0):
        raise ConfigError(
            "Servono 0 < bottom_knee_angle < standing_knee_angle <= 180"
        )
    if v.threshold_hysteresis_degrees < 0:
        raise ConfigError("vision.threshold_hysteresis_degrees deve essere >= 0")
    # L'isteresi non puo' chiudere la banda fra le due soglie.
    band = v.standing_knee_angle_degrees - v.bottom_knee_angle_degrees
    if v.threshold_hysteresis_degrees * 2 >= band:
        raise ConfigError(
            "threshold_hysteresis troppo ampia rispetto alla banda "
            "standing-bottom: le soglie si sovrappongono"
        )
    _positive("vision.standing_stability_seconds", v.standing_stability_seconds)

    _positive("safety.emergency_bypass_hold_seconds", cfg.safety.emergency_bypass_hold_seconds)

    if cfg.dev_work_interval_seconds is not None:
        _positive("dev_work_interval_seconds", cfg.dev_work_interval_seconds)


def _coerce(section: dict[str, Any] | None, dataclass_type: type) -> dict[str, Any]:
    """Estrae dal dict solo i campi noti del dataclass, ignorando il resto."""
    if not section:
        return {}
    known = {f.name for f in dataclass_type.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return {k: v for k, v in section.items() if k in known}


def from_dict(data: dict[str, Any] | None) -> AppConfig:
    """Costruisce AppConfig da un dict (es. YAML caricato). Privacy forzata."""
    data = data or {}

    if "privacy" in data and data["privacy"]:
        unsafe = {k: v for k, v in data["privacy"].items() if v is True}
        if unsafe:
            logger.warning(
                "Valori privacy ignorati (forzati a OFF nel codice): %s",
                ", ".join(sorted(unsafe)),
            )

    cfg = AppConfig(
        schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        enabled=bool(data.get("enabled", True)),
        timer=TimerConfig(**_coerce(data.get("timer"), TimerConfig)),
        workout=WorkoutConfig(**_coerce(data.get("workout"), WorkoutConfig)),
        vision=VisionConfig(**_coerce(data.get("vision"), VisionConfig)),
        privacy=PrivacyConfig(),  # SEMPRE i default sicuri, mai dal file
        startup=StartupConfig(**_coerce(data.get("startup"), StartupConfig)),
        safety=SafetyConfig(**_coerce(data.get("safety"), SafetyConfig)),
    )
    validate(cfg)
    return cfg


def load_config(path: str | Path | None = None) -> AppConfig:
    """Carica la config da YAML. Se il file manca, ritorna i default validati."""
    if path is None:
        return from_dict({})
    p = Path(path)
    if not p.exists():
        logger.info("Config %s assente: uso i default.", p)
        return from_dict({})
    import yaml

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - dipende dal file
        raise ConfigError(f"YAML non valido in {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"La config in {p} non e' una mappa YAML")
    return from_dict(raw)


def with_dev_interval(cfg: AppConfig, seconds: float | None) -> AppConfig:
    """Ritorna una copia con override dev dell'intervallo (non persistito)."""
    new = replace(cfg, dev_work_interval_seconds=seconds)
    validate(new)
    return new
