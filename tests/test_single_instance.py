import pytest

from workout_gate.single_instance import AlreadyRunning, SingleInstance


def test_second_instance_is_blocked(tmp_path):
    lock = tmp_path / "app.lock"
    first = SingleInstance(lock).acquire()
    try:
        with pytest.raises(AlreadyRunning):
            SingleInstance(lock).acquire()
    finally:
        first.release()


def test_reacquire_after_release(tmp_path):
    lock = tmp_path / "app.lock"
    a = SingleInstance(lock).acquire()
    a.release()
    b = SingleInstance(lock).acquire()
    b.release()


def test_context_manager(tmp_path):
    lock = tmp_path / "app.lock"
    with SingleInstance(lock):
        with pytest.raises(AlreadyRunning):
            SingleInstance(lock).acquire()
    # fuori dal with il lock e' rilasciato
    SingleInstance(lock).acquire().release()
