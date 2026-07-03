import inspect
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "site_adapter.py.example"


def _load_namespace():
    source = EXAMPLE.read_text(encoding="utf-8")
    namespace = {}
    exec(compile(source, str(EXAMPLE), "exec"), namespace)
    return namespace


def test_example_exists_and_compiles():
    ns = _load_namespace()
    assert callable(ns["discover"])
    assert callable(ns["parse"])


def test_functions_match_the_engine_contract():
    # scrape.py does `from site_adapter import discover, parse` and calls
    # discover(cfg) / parse(html, url); the stub must show those signatures.
    ns = _load_namespace()
    assert list(inspect.signature(ns["discover"]).parameters) == ["cfg"]
    assert list(inspect.signature(ns["parse"]).parameters) == ["html", "url"]


def test_stub_fails_loud_if_copied_unimplemented():
    # If the stub is copied to site_adapter.py and run as-is, it must raise
    # with an actionable message, not silently return an empty catalog.
    ns = _load_namespace()
    with pytest.raises(NotImplementedError):
        ns["discover"]({})
    with pytest.raises(NotImplementedError):
        ns["parse"]("<html></html>", "https://x/p")
