# tests/test_signals.py
from jemscrape.signals import detect_render, detect_auth, detect_antibot, analyze_shape
from jemscrape.fetch import Probe
from jemscrape.normalize import normalize


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
    out = detect_antibot(Probe(status=503, headers={"cf-ray": "abc"},
                               body="Checking your browser before accessing the store.",
                               final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "cloudflare"


def test_detect_antibot_geo_block_body():
    out = detect_antibot(Probe(status=200, headers={}, body="This content is not available in your country.", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "geo"


def test_detect_antibot_clean():
    out = detect_antibot(Probe(status=200, headers={}, body="<h1>Widget</h1>", final_url="https://x/p"))
    assert out["blocked"] is False and out["kind"] is None


def test_detect_antibot_cfray_on_normal_200_is_not_blocked():
    # cf-ray is present on EVERY Cloudflare-proxied response, including normal
    # 200s — it must NOT by itself mean "blocked", or every page of a
    # Cloudflare-fronted site would be falsely skipped by the warm-up.
    out = detect_antibot(Probe(status=200, headers={"cf-ray": "abc"},
                               body="<h1>Fire-Lite ES-200X</h1>", final_url="https://x/p"))
    assert out["blocked"] is False and out["kind"] is None


def test_detect_antibot_cf_mitigated_header_is_blocked():
    # cf-mitigated is only set when Cloudflare actually challenged/mitigated.
    out = detect_antibot(Probe(status=403, headers={"cf-mitigated": "challenge"},
                               body="", final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "cloudflare"


def test_detect_antibot_cf_challenge_body_ignored_on_200():
    # A real Cloudflare challenge is never a plain 200 with content; a 200 that
    # merely contains the phrase must not be flagged as blocked.
    out = detect_antibot(Probe(status=200, headers={},
                               body="Just a moment while we set things up.",
                               final_url="https://x/p"))
    assert out["blocked"] is False


def test_detect_antibot_rendered_cf_challenge_at_200_is_blocked():
    # A browser-rendered Cloudflare JS challenge returns HTTP 200 (Playwright
    # follows the challenge page as a normal navigation) with no special
    # headers (headers={} since Playwright doesn't surface raw response
    # headers the same way). The challenge-specific body markers must still
    # be trusted regardless of status, or browser-mode probes silently miss
    # every JS-challenge block.
    out = detect_antibot(Probe(status=200, headers={},
                               body="Checking your browser before accessing. cf-browser-verification",
                               final_url="https://x/p"))
    assert out["blocked"] is True and out["kind"] == "cloudflare"


def test_detect_antibot_access_phrase_in_200_product_body_not_blocked():
    # "access denied" is a generic phrase that legitimately appears in product
    # copy (e.g. access-control hardware); a 200 product page must not be
    # misread as a block.
    out = detect_antibot(Probe(status=200, headers={},
                               body="<p>Prevents access denied faults on the control panel.</p>",
                               final_url="https://x/p"))
    assert out["blocked"] is False


def _rec(pid, name, prices=None, images=None, breadcrumbs=None):
    return normalize(
        {"product_id": pid, "name": name, "sku": pid,
         "prices": prices or [], "images": images or [], "breadcrumbs": breadcrumbs or []},
        source_site="x", source_url="https://x/p", scraped_at="t",
        authorization_ref="a", raw_ref="r")


def test_analyze_shape_empty():
    out = analyze_shape([])
    assert out["count"] == 0


def test_analyze_shape_coverage_and_bands_and_collisions():
    records = [
        _rec("A1", "Widget", prices=[{"band": "trade", "value": 10}], images=["u"], breadcrumbs=["Fire"]),
        _rec("A1", "Widget v2", prices=[{"band": "list", "value": 12}]),   # same product_id -> collision
        _rec("B2", "Gadget"),                                              # no price/image/breadcrumb
    ]
    out = analyze_shape(records)
    assert out["count"] == 3
    assert out["coverage"]["name"] == 1.0
    assert out["coverage"]["price"] == round(2 / 3, 3)
    assert out["price_bands"] == ["list", "trade"]
    assert out["variant_collisions"] == 1
