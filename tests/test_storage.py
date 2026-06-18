import json

from workout_gate.storage import JsonStore, default_state


def test_roundtrip(tmp_path):
    s = JsonStore(tmp_path / "db.json")
    d = s.load()
    assert d["accumulated_active_seconds"] == 0.0
    d["total_squats"] = 10
    d["accumulated_active_seconds"] = 123.5
    s.save(d)
    again = s.load()
    assert again["total_squats"] == 10
    assert again["accumulated_active_seconds"] == 123.5


def test_defaults_when_missing(tmp_path):
    assert JsonStore(tmp_path / "nope.json").load() == default_state()


def test_corrupt_file_recovers_to_defaults(tmp_path):
    p = tmp_path / "db.json"
    p.write_text("{ this is not json", encoding="utf-8")
    s = JsonStore(p)
    d = s.load()
    assert d["schema_version"] == 1
    assert (tmp_path / "db.json.corrupt").exists()


def test_atomic_write_leaves_no_tmp(tmp_path):
    s = JsonStore(tmp_path / "db.json")
    s.save(default_state())
    assert list(tmp_path.glob("*.tmp")) == []


def test_update_merges(tmp_path):
    s = JsonStore(tmp_path / "db.json")
    s.update(total_squats=5)
    s.update(workouts_completed=2)
    d = s.load()
    assert d["total_squats"] == 5
    assert d["workouts_completed"] == 2


def test_migration_from_old_schema(tmp_path):
    p = tmp_path / "db.json"
    p.write_text(json.dumps({"schema_version": 0, "total_squats": 3}), encoding="utf-8")
    d = JsonStore(p).load()
    assert d["schema_version"] == 1
    assert d["total_squats"] == 3
    assert "streak_current" in d  # i campi mancanti vengono colmati


def test_unknown_top_level_type_recovers(tmp_path):
    p = tmp_path / "db.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")  # lista, non oggetto
    d = JsonStore(p).load()
    assert d == default_state()
