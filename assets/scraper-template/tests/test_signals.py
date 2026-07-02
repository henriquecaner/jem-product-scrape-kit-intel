# tests/test_signals.py
from jemscrape.signals import detect_render, detect_auth, detect_antibot
from jemscrape.fetch import Probe


def test_detect_render_server_rendered_page():
    body = "<html><body><h1>Fire-Lite ES-200X</h1>" + ("<p>Addressable panel. </p>" * 40) + "</body></html>"
    out = detect_render(body)
    assert out["mode"] == "server"
    assert out["text_len"] > 200


def test_detect_render_spa_shell():
    body = '<html><body><div id="root"></div><script>' + ("x=1;" * 500) + "</script></body></html>"
    out = detect_render(body)
    assert out["mode"] == "spa"
    assert 'id="root"' in out["markers"]


def test_detect_render_reports_script_ratio():
    spa_body = '<html><body><div id="root"></div><script>' + ("x=1;" * 500) + "</script></body></html>"
    spa_out = detect_render(spa_body)
    assert 0.9 < spa_out["script_ratio"] < 1.0

    server_body = "<html><body><h1>Fire-Lite ES-200X</h1>" + ("<p>Addressable panel. </p>" * 40) + "</body></html>"
    server_out = detect_render(server_body)
    assert server_out["script_ratio"] == 0.0


def _probe(status=200, final_url="https://x/product/1", body=""):
    return Probe(status=status, headers={}, body=body, final_url=final_url)


def test_detect_auth_flags_403():
    out = detect_auth(_probe(status=403))
    assert out["auth_required"] is True


def test_detect_auth_flags_401():
    out = detect_auth(_probe(status=401))
    assert out["auth_required"] is True


def test_detect_auth_flags_login_redirect():
    out = detect_auth(_probe(final_url="https://x/account/login?next=/p"))
    assert out["auth_required"] is True


def test_detect_auth_flags_price_login_body():
    out = detect_auth(_probe(body="<div>Sign in to see price</div>"))
    assert out["auth_required"] is True


_LOGIN_BODY_MARKERS = (
    "sign in to see price",
    "log in to view",
    "please sign in",
    "login required",
    "member price",
    'type="password"',
)


def test_detect_auth_flags_every_login_body_marker():
    for marker in _LOGIN_BODY_MARKERS:
        body = f"<div>prefix {marker} suffix</div>"
        out = detect_auth(_probe(body=body))
        assert out["auth_required"] is True, f"marker {marker!r} did not trigger auth_required"
        assert any(marker in s for s in out["signals"]), f"marker {marker!r} not reported in signals"


def test_detect_auth_clean_product_page():
    out = detect_auth(_probe(body="<h1>Widget</h1><span>$19.99</span>"))
    assert out["auth_required"] is False


def test_detect_antibot_429_rate():
    out = detect_antibot(Probe(status=429, headers={}, body="", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "rate"


def test_detect_antibot_cloudflare_header():
    out = detect_antibot(Probe(status=503, headers={"cf-ray": "abc"}, body="Just a moment...", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "cloudflare"


def test_detect_antibot_geo_block_body():
    out = detect_antibot(Probe(status=200, headers={}, body="This content is not available in your country.", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "geo"


def test_detect_antibot_clean():
    out = detect_antibot(Probe(status=200, headers={}, body="<h1>Widget</h1>", final_url="https://x/p"))
    assert out["blocked"] is False and out["kind"] is None
