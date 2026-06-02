from pathlib import Path

from census_mcp.store import Store, default_store_path


def test_default_store_path_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CENSUS_MCP_STORE", "/tmp/custom/acs.sqlite3")
    assert default_store_path() == Path("/tmp/custom/acs.sqlite3")


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
