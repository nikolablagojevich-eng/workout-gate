"""Garanzia di singola istanza tramite lock su file.

Su Windows usa ``msvcrt.locking`` (lock per-handle, non advisory): un secondo
processo che prova a bloccare lo stesso byte fallisce. Su POSIX usa ``fcntl``.
Cosi' due istanze concorrenti non possono partire entrambe.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import IO


class AlreadyRunning(RuntimeError):
    """Un'altra istanza di Workout Gate detiene gia' il lock."""


class SingleInstance:
    def __init__(self, lock_path: str | Path) -> None:
        self.lock_path = Path(lock_path)
        self._fh: IO | None = None

    def acquire(self) -> SingleInstance:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "a+")
        try:
            self._lock(self._fh)
        except OSError as exc:
            self._fh.close()
            self._fh = None
            raise AlreadyRunning(
                f"Workout Gate e' gia' in esecuzione (lock: {self.lock_path})"
            ) from exc
        # Scrive il PID (informativo).
        try:
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(str(os.getpid()))
            self._fh.flush()
        except OSError:
            pass
        return self

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self._unlock(self._fh)
        finally:
            try:
                self._fh.close()
            finally:
                self._fh = None

    @staticmethod
    def _lock(fh) -> None:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - non Windows
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]

    @staticmethod
    def _unlock(fh) -> None:
        if os.name == "nt":
            import msvcrt

            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:  # pragma: no cover - non Windows
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]

    def __enter__(self) -> SingleInstance:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
