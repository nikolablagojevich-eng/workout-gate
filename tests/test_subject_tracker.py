from workout_gate.vision.subject_tracker import Candidate, SubjectTracker


def big_center() -> Candidate:
    return Candidate(cx=0.5, cy=0.5, width=0.3, height=0.7)


def small_corner() -> Candidate:
    return Candidate(cx=0.1, cy=0.1, width=0.05, height=0.1)  # area 0.005


def test_picks_largest_central():
    t = SubjectTracker()
    r = t.select([small_corner(), big_center()])
    assert r.present is True
    assert r.index == 1


def test_central_beats_offcenter_same_size():
    t = SubjectTracker()
    central = Candidate(0.5, 0.5, 0.3, 0.6)
    offcenter = Candidate(0.9, 0.9, 0.3, 0.6)
    r = t.select([offcenter, central])
    assert r.index == 1


def test_ignores_small_background_person():
    t = SubjectTracker(min_area=0.05)
    r = t.select([small_corner()])  # sotto min_area
    assert r.present is False
    assert r.index is None


def test_continuity_keeps_main_when_both_present():
    t = SubjectTracker()
    t.select([big_center()])  # acquisizione
    r = t.select([Candidate(0.52, 0.5, 0.3, 0.7), small_corner()])
    assert r.changed is False
    assert r.present is True
    assert r.index == 0


def test_resets_after_main_disappears():
    t = SubjectTracker(lost_grace_frames=2)
    t.select([big_center()])
    last = None
    for _ in range(4):
        last = t.select([small_corner()])  # solo sfondo -> filtrato
    assert last.present is False
    # un nuovo soggetto principale appare: acquisizione fresca
    fresh = t.select([Candidate(0.5, 0.5, 0.3, 0.7)])
    assert fresh.changed is True
    assert fresh.present is True


def test_first_acquisition_flags_changed():
    t = SubjectTracker()
    r = t.select([big_center()])
    assert r.changed is True
    assert r.present is True
