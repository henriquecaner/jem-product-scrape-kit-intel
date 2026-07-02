# tests/test_signals.py
from jemscrape.signals import detect_render, detect_auth
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


def test_detect_auth_flags_login_redirect():
    out = detect_auth(_probe(final_url="https://x/account/login?next=/p"))
    assert out["auth_required"] is True


def test_detect_auth_flags_price_login_body():
    out = detect_auth(_probe(body="<div>Sign in to see price</div>"))
    assert out["auth_required"] is True


def test_detect_auth_clean_product_page():
    out = detect_auth(_probe(body="<h1>Widget</h1><span>$19.99</span>"))
    assert out["auth_required"] is False
