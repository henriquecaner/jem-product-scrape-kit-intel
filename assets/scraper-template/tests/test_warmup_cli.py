import json
from datetime import datetime, timezone, timedelta

import warmup
from jemscrape.fetch import Probe
from jemscrape.browser import RenderedResult

SERVER_BODY = "<html><body><h1>Widget</h1>" + ("<p>d </p>" * 40) + "</body></html>"


def _write_valid_gate_files(tmp_path):
    now = datetime.now(timezone.utc)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "target_domain": "example.com", "runtime": "local",
        "user_agent": "UA", "rate_limit_floor_seconds": 8,
    }), encoding="utf-8")
    authz = tmp_path / ".scrape-authorization.json"
    authz.write_text(json.dumps({
        "target_domain": "example.com", "authorization_type": "public_competitor",
        "approver": "H", "approved_at": now.isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "rate_limit_floor_seconds": 8, "robots_status": "allowed",
        "robots_override_ref": None, "requires_approval": False, "scope": "https://example.com/",
    }), encoding="utf-8")
    return cfg, authz


def _auth_config(tmp_path, *, auth_required):
    now = datetime.now(timezone.utc)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "target_domain": "x.com", "runtime": "local",
        "user_agent": "UA", "rate_limit_floor_seconds": 8,
        "auth_required": auth_required, "login_url": "https://x.com/login",
    }), encoding="utf-8")
    authz = tmp_path / ".scrape-authorization.json"
    authz.write_text(json.dumps({
        "target_domain": "x.com", "authorization_type": "public_competitor",
        "approver": "H", "approved_at": now.isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "rate_limit_floor_seconds": 8, "robots_status": "allowed",
        "robots_override_ref": None, "requires_approval": False, "scope": "https://x.com/",
    }), encoding="utf-8")
    return cfg, authz


def test_warmup_auth_required_missing_session_returns_2(tmp_path, capsys, monkeypatch):
    # Build a minimal valid config with auth_required + a passing compliance gate.
    cfg_path, authz_path = _auth_config(tmp_path, auth_required=True)
    sample = tmp_path / "sample.json"
    sample.write_text('["https://x.com/p"]', encoding="utf-8")
    rc = __import__("warmup").main(
        ["--sample", str(sample), "--config", str(cfg_path), "--authz", str(authz_path),
         "--out", str(tmp_path / "out.json")],
        parse_fn=lambda html, url: None)
    assert rc == 2
    assert "session" in capsys.readouterr().err.lower()


def test_warmup_cli_success_writes_report(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/product/1"]), encoding="utf-8")
    out = tmp_path / ".scrape-warmup-report.json"

    def fake_probe(url):
        return Probe(status=200, headers={}, body=SERVER_BODY, final_url=url)

    def fake_parse(body, url):
        return {"product_id": "A1", "name": "Widget", "sku": "A1"}

    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg), "--authz", str(authz), "--out", str(out)],
        probe_fn=fake_probe, parse_fn=fake_parse)
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fetched"] == 1


def test_warmup_cli_blocked_by_gate_returns_2(tmp_path, capsys):
    # No authz file -> compliance gate fails closed.
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "target_domain": "example.com", "runtime": "local",
        "user_agent": "UA", "rate_limit_floor_seconds": 8}), encoding="utf-8")
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/p"]), encoding="utf-8")
    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg),
         "--authz", str(tmp_path / "missing.json"), "--out", str(tmp_path / "r.json")],
        probe_fn=lambda u: None, parse_fn=lambda b, u: None)
    assert rc == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_warmup_cli_missing_sample_returns_2(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    rc = warmup.main(
        ["--sample", str(tmp_path / "nope.json"), "--config", str(cfg),
         "--authz", str(authz), "--out", str(tmp_path / "r.json")],
        probe_fn=lambda u: None, parse_fn=lambda b, u: None)
    assert rc == 2


def test_warmup_cli_browser_mode_malformed_proxy_returns_2(tmp_path, capsys, monkeypatch):
    # A host-less HTTPS_PROXY (e.g. a broken Actions secret) must fail closed
    # with a clean [warmup] BLOCKED message, not an uncaught traceback.
    monkeypatch.setenv("HTTPS_PROXY", "http://:8080")
    cfg, authz = _write_valid_gate_files(tmp_path)
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/product/1"]), encoding="utf-8")
    out = tmp_path / "r.json"

    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg), "--authz", str(authz),
         "--out", str(out), "--render", "browser"],
        parse_fn=lambda body, url: None)

    assert rc == 2
    assert "[warmup] BLOCKED" in capsys.readouterr().err


def test_warmup_cli_browser_mode_uses_render_fn(tmp_path):
    cfg, authz = _write_valid_gate_files(tmp_path)
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(["https://example.com/product/1"]), encoding="utf-8")
    out = tmp_path / "r.json"
    rendered = "<html><body><h1>Widget</h1>" + ("<p>d </p>" * 40) + "</body></html>"

    def fake_render(url):
        return RenderedResult(status=200, html=rendered, final_url=url)

    def fake_parse(body, url):
        assert "Widget" in body      # proves the browser-rendered html reached parse
        return {"product_id": "A1", "name": "Widget", "sku": "A1"}

    rc = warmup.main(
        ["--sample", str(sample), "--config", str(cfg), "--authz", str(authz),
         "--out", str(out), "--render", "browser"],
        render_fn=fake_render, parse_fn=fake_parse)

    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fetched"] == 1
    assert data["shape"]["count"] == 1
