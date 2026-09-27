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


def test_exact_match_beats_high_priority_bad_variant():
    m = Manager({
        "first": FakeProvider("first", [{"provider_id":"first","track_id":"1","artist":"Massive Attack","title":"Teardrop (Live)","album":"Live"}]),
        "second": FakeProvider("second", [{"provider_id":"second","track_id":"2","artist":"Massive Attack","title":"Teardrop","album":"Mezzanine"}]),
    })
    r = UniversalResolver(m)
    out = r.resolve({"artist":"Massive Attack","title":"Teardrop","album":"Mezzanine"})
    assert out["provider_id"] == "second"
    assert out["track_id"] == "2"


def test_priority_breaks_near_tie():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Autechre","title":"Bike"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Autechre","title":"Bike"}]),
    })
    m.settings["provider_priority"] = ["b", "a"]
    out = UniversalResolver(m).resolve({"artist":"Autechre","title":"Bike"})
    assert out["provider_id"] == "b"


def test_blocklist_skips_only_bad_candidate():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Boards of Canada","title":"Roygbiv"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Boards of Canada","title":"Roygbiv"}]),
    })
    r = UniversalResolver(m)
    target = {"artist":"Boards of Canada","title":"Roygbiv"}
    r.block(target, m.providers["a"].rows[0])
    out = r.resolve(target)
    assert out["provider_id"] == "b"
    assert m.saved == 1


def test_direct_provider_identity_stays_direct():
    m = Manager({"a": FakeProvider("a", [])})
    r = UniversalResolver(m)
    out = r.resolve({"provider_id":"a","track_id":"123","artist":"X","title":"Y"})
    assert out["provider_id"] == "a"
    assert out["_resolution"]["mode"] == "direct"


def test_resolve_many_keeps_failures_separate():
    m = Manager({"a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"One","title":"Found"}])})
    r = UniversalResolver(m)
    result = r.resolve_many([
        {"artist":"One","title":"Found"},
        {"artist":"Nobody","title":"Missing"},
    ])
    assert len(result["tracks"]) == 1
    assert len(result["unresolved"]) == 1
