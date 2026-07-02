from pathlib import Path

GI = (Path(__file__).resolve().parents[2] / "project-skeleton" / ".gitignore").read_text(encoding="utf-8")


def test_gitignore_blocks_cache_and_secrets():
    for pat in ["/data/", ".scrape-authorization.json", ".scrape-warmup.json", "*.token", ".env"]:
        assert pat in GI


def test_gitignore_data_rule_is_root_anchored():
    # An unanchored `data/` would also ignore exports/wiki/data/... (a product
    # category named "data"), silently dropping deliverables. Must be /data/.
    lines = [l.strip() for l in GI.splitlines() if l.strip() and not l.strip().startswith("#")]
    assert "/data/" in lines
    assert "data/" not in lines   # no bare, unanchored data/ rule


def test_gitignore_does_not_block_deliverables():
    ignore_lines = [l.strip() for l in GI.splitlines() if l.strip() and not l.strip().startswith("#")]
    for pat in ["exports/", "state/", "wiki/", "exports", "state", "wiki"]:
        assert pat not in ignore_lines
