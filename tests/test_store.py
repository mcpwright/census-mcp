from pathlib import Path

from census_mcp.store import Store


def test_default_store_path_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CENSUS_MCP_STORE", "/tmp/custom/acs.sqlite3")
    assert Store.default_path() == Path("/tmp/custom/acs.sqlite3")


def test_default_store_path_uses_census_app_dir(monkeypatch) -> None:
    monkeypatch.delenv("CENSUS_MCP_STORE", raising=False)
    p = Store.default_path()
    assert p.name == "acs.sqlite3"
    assert p.parent.name == "mcpwright-census"


def test_roundtrip_and_state(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    assert s.is_loaded() is False
    assert s.vintage() is None

    rows: list[dict[str, object]] = [
        {"zcta": "12345", "population": 5000, "name": "ZCTA5 12345"}
    ]
    n = s.replace_all(rows, 2023)
    assert n == 1
    assert s.is_loaded() is True
    assert s.vintage() == 2023

    rec = s.get("12345")
    assert rec is not None
    assert rec["zcta"] == "12345"
    assert rec["population"] == 5000
    assert rec["name"] == "ZCTA5 12345"

    assert s.get("00000") is None  # absent ZCTA
    s.close()


def test_replace_all_is_atomic_rebuild(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_all([{"zcta": "11111", "population": 1}], 2022)
    s.replace_all([{"zcta": "22222", "population": 2}], 2023)
    # The second load fully replaces the first.
    assert s.get("11111") is None
    assert s.get("22222") is not None
    assert s.vintage() == 2023
    s.close()


_PLACES: list[dict[str, object]] = [
    {
        "zcta": "02138",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "MA",
        "coverage": 0.55,
    },
    {
        "zcta": "02139",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "MA",
        "coverage": 0.40,
    },
    {
        "zcta": "43725",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "OH",
        "coverage": 0.90,
    },
]


def test_places_roundtrip_and_state(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    assert s.places_loaded() is False
    assert s.place_vintage() is None

    n = s.replace_places(_PLACES, 2020)
    assert n == 3
    assert s.places_loaded() is True
    assert s.place_vintage() == 2020
    s.close()


def test_find_places_ranks_by_coverage_desc(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places(_PLACES, 2020)
    # Both the key ("cambridge") and full name ("cambridge city") should match.
    rows = s.find_places("cambridge city", "cambridge")
    assert [r["zcta"] for r in rows] == ["43725", "02138", "02139"]  # 0.90, 0.55, 0.40
    s.close()


def test_find_places_state_filter(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places(_PLACES, 2020)
    rows = s.find_places("cambridge city", "cambridge", state="MA")
    assert [r["zcta"] for r in rows] == ["02138", "02139"]
    assert all(r["state"] == "MA" for r in rows)
    s.close()


def test_find_places_no_match_returns_empty(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places(_PLACES, 2020)
    assert s.find_places("nowhere", "nowhere") == []
    s.close()


# Two distinct places whose descriptor-stripped keys collide on "foo": a place
# literally named "Foo City" vs an unrelated "Foo town".
_COLLISION: list[dict[str, object]] = [
    {
        "zcta": "10001",
        "name_display": "Foo City",
        "name_norm": "foo city",
        "name_key": "foo",
        "state": "NY",
        "coverage": 0.9,
    },
    {
        "zcta": "20002",
        "name_display": "Foo town",
        "name_norm": "foo town",
        "name_key": "foo",
        "state": "PA",
        "coverage": 0.8,
    },
]


def test_find_places_descriptor_query_does_not_cross_match(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places(_COLLISION, 2020)
    # "Foo City" carries a descriptor -> exact full-name match only; it must NOT
    # pull in "Foo town" just because both reduce to the key "foo".
    rows = s.find_places("foo city", "foo")
    assert [r["zcta"] for r in rows] == ["10001"]
    # A bare "Foo" legitimately matches both via the stripped key.
    bare = s.find_places("foo", "foo")
    assert {r["zcta"] for r in bare} == {"10001", "20002"}
    s.close()


def test_find_places_state_with_no_match_is_empty(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places(_PLACES, 2020)
    assert s.find_places("cambridge city", "cambridge", state="TX") == []
    s.close()


def test_replace_places_is_atomic_rebuild(tmp_path: Path) -> None:
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_places([dict(_PLACES[0])], 2010)
    s.replace_places([dict(_PLACES[2])], 2020)
    assert [r["zcta"] for r in s.find_places("cambridge city", "cambridge")] == [
        "43725"
    ]
    assert s.place_vintage() == 2020
    s.close()
