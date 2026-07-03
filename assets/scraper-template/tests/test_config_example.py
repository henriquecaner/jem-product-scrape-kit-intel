import json
from pathlib import Path

from jemscrape.config import validate_config

EXAMPLE = Path(__file__).resolve().parents[1] / "config.json.example"


def _example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_passes_validation():
    validate_config(_example())  # no raise


def test_example_declares_fetch_mode_http():
    assert _example()["fetch_mode"] == "http"


def test_example_includes_dataset_reconciliation_keys():
    # build_dataset.py reads these with empty defaults; if the example omits
    # them, a scaffolded project silently skips price-band/hub-stock/variant
    # reconciliation. The example must document their shape.
    cfg = _example()
    assert cfg["band_priority"] == []
    assert cfg["hub_group"] == []
    assert cfg["ireland_branch"] == ""


def test_config_example_documents_auth_fields():
    cfg = _example()
    assert "auth_required" in cfg
    assert "login_url" in cfg
