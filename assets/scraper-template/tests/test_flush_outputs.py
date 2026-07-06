import json
import scrape
from jemscrape.manifest import Manifest


def _manifest(url, name):
    m = Manifest()
    m.record_scraped(url, {"name": name})
    return m


def test_flush_accumulates_across_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "HERE", tmp_path)
    cache_dir = tmp_path / "data"
    cache_dir.mkdir()

    p1 = scrape.flush_outputs(_manifest("https://x/1", "one"), cache_dir)
    assert p1 == tmp_path / "state" / "raw_records.json"
    p2 = scrape.flush_outputs(_manifest("https://x/2", "two"), cache_dir)

    data = json.loads(p2.read_text(encoding="utf-8"))
    assert sorted(r["url"] for r in data) == ["https://x/1", "https://x/2"]


def test_flush_recovers_from_corrupt_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scrape, "HERE", tmp_path)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "raw_records.json").write_text("{ not json", encoding="utf-8")
    cache_dir = tmp_path / "data"
    cache_dir.mkdir()

    p = scrape.flush_outputs(_manifest("https://x/1", "one"), cache_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert [r["url"] for r in data] == ["https://x/1"]
    assert "starting fresh" in capsys.readouterr().err  # fail-open warning emitted
