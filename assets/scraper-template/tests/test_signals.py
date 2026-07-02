# tests/test_signals.py
from jemscrape.signals import detect_render


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
