from melodex.resolver import UniversalResolver


class FakeProvider:
    def __init__(self, pid, rows):
        self.pid = pid
        self.rows = rows
    def search(self, query, limit=50):
        return [dict(x) for x in self.rows[:limit]]
    def resolve(self, track):
        out = dict(track)
        out.setdefault("stream_url", f"https://example.invalid/{self.pid}/{out.get('track_id')}")
        return out


class Manager:
    def __init__(self, providers):
        self.providers = providers
        self.settings = {}
        self.saved = 0
    def save(self):
        self.saved += 1


def test_inspector_exposes_scores_reasons_and_flags():
    m = Manager({
        "a": FakeProvider("a", [
            {"provider_id":"a","track_id":"1","artist":"Massive Attack","title":"Teardrop (Live)","album":"Live","duration":330},
            {"provider_id":"a","track_id":"2","artist":"Massive Attack","title":"Teardrop","album":"Mezzanine","duration":331},
        ])
    })
    r = UniversalResolver(m)
    info = r.inspect({"artist":"Massive Attack","title":"Teardrop","album":"Mezzanine","duration":331})
    assert info["candidates"]
    top = info["candidates"][0]
    assert top["track"]["track_id"] == "2"
    assert "exact title" in top["reasons"]
    live = next(x for x in info["candidates"] if x["track"]["track_id"] == "1")
    assert "live" in live["flags"]
    assert live["version_penalty"] > 0


def test_preferred_match_is_persistent_and_beats_provider_priority():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Autechre","title":"Bike"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Autechre","title":"Bike"}]),
    })
    target = {"artist":"Autechre","title":"Bike"}
    r = UniversalResolver(m)
    r.prefer(target, m.providers["b"].rows[0])
    assert m.settings["resolver_preferences"][0]["candidate"] == "b:2"
    out = r.resolve(target)
    assert out["provider_id"] == "b"
    assert out["track_id"] == "2"
    assert out["_resolution"]["mode"] == "preferred"


def test_blocking_preferred_candidate_clears_preference_and_uses_next():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Boards of Canada","title":"Roygbiv"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Boards of Canada","title":"Roygbiv"}]),
    })
    target = {"artist":"Boards of Canada","title":"Roygbiv"}
    r = UniversalResolver(m)
    r.prefer(target, m.providers["a"].rows[0])
    r.block(target, m.providers["a"].rows[0])
    assert r.preferred_entry(target) is None
    out = r.resolve(target)
    assert out["provider_id"] == "b"


def test_duration_can_break_otherwise_equal_match():
    m = Manager({
        "a": FakeProvider("a", [
            {"provider_id":"a","track_id":"wrong","artist":"Artist","title":"Track","duration":500},
            {"provider_id":"a","track_id":"right","artist":"Artist","title":"Track","duration":202},
        ])
    })
    r = UniversalResolver(m)
    rows = r.candidates({"artist":"Artist","title":"Track","duration":202})
    assert rows[0].track["track_id"] == "right"
    assert rows[0].duration_adjustment > 0


def test_resolve_exact_marks_manual_resolution():
    m = Manager({"a": FakeProvider("a", [])})
    r = UniversalResolver(m)
    out = r.resolve_exact(
        {"provider_id":"a","track_id":"44","artist":"X","title":"Y"},
        {"artist":"Requested X","title":"Requested Y"},
    )
    assert out["_resolution"]["mode"] == "manual"
    assert out["_resolution"]["requested"]["title"] == "Requested Y"
