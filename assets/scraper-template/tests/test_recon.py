import json

from jemscrape.recon import build_checklist, run_warmup, write_report, WarmupReport
from jemscrape.fetch import Probe
from jemscrape.errors import FetchError

SPA_BODY = '<html><body><div id="root"></div><script>' + ("x=1;" * 500) + "</script></body></html>"
SERVER_BODY = "<html><body><h1>Widget</h1>" + ("<p>desc </p>" * 40) + "</body></html>"


def _fake_probe(mapping):
    def probe_fn(url):
        val = mapping[url]
        if isinstance(val, Exception):
            raise val
        return val
    return probe_fn


def _parse(body, url):
    # Minimal fake site adapter: returns a raw record only for the server page.
    if "Widget" in body:
        return {"product_id": "A1", "name": "Widget", "sku": "A1",
                "prices": [{"band": "trade", "value": 10}]}
    return None


def test_run_warmup_aggregates_signals_and_shape():
    # The auth-blocked page reuses SERVER_BODY (contains "Widget", plenty of
    # visible text -> detect_render says "server") so _parse WOULD happily
    # return a record for it. Proving auth_count/shape stay right here proves
    # the auth gate in run_warmup suppresses parsing, not just parser content.
    mapping = {
        "https://x/spa": Probe(status=200, headers={}, body=SPA_BODY, final_url="https://x/spa"),
        "https://x/server": Probe(status=200, headers={}, body=SERVER_BODY, final_url="https://x/server"),
        "https://x/auth": Probe(status=403, headers={}, body=SERVER_BODY, final_url="https://x/account/login"),
        "https://x/dead": FetchError("boom"),
        "https://x/blocked": Probe(status=429, headers={}, body="", final_url="https://x/blocked"),
    }
    report = run_warmup(
        list(mapping.keys()), probe_fn=_fake_probe(mapping), parse_fn=_parse,
        source_site="x", scraped_at="t", authorization_ref="a")
    assert report.sampled == 5
    assert report.fetched == 4          # dead one raised
    assert report.fetch_errors == 1
    assert report.spa_count == 1
    assert report.auth_count == 1
    assert report.antibot_count == 1
    assert report.shape["count"] == 1   # only the server page parsed+normalized
    assert any("SPA" in c or "JS" in c for c in report.checklist)


def test_run_warmup_records_parse_error_without_aborting():
    # A malformed raw dict (missing product_id/name) makes normalize()'s
    # rec.validate() raise ValueError. That must not abort the whole warm-up
    # run -- it should be recorded per-URL and counted, while the other
    # sampled URL's signal data is preserved.
    def parse_fn(body, url):
        if url == "https://x/bad":
            return {"name": ""}
        return _parse(body, url)

    mapping = {
        "https://x/bad": Probe(status=200, headers={}, body=SERVER_BODY, final_url="https://x/bad"),
        "https://x/good": Probe(status=200, headers={}, body=SERVER_BODY, final_url="https://x/good"),
    }
    report = run_warmup(
        list(mapping.keys()), probe_fn=_fake_probe(mapping), parse_fn=parse_fn,
        source_site="x", scraped_at="t", authorization_ref="a")
    assert report.parse_errors == 1
    assert report.shape["count"] == 1
    bad_entry = next(e for e in report.per_url if e["url"] == "https://x/bad")
    assert "parse_error" in bad_entry


def test_checklist_antibot_mitigation_matches_v1_runtimes():
    # v1 has no VM runtime path (session/VM promotion is Plano 3b, deferred).
    # The operator-facing mitigation must point at what exists: country proxy
    # on the GitHub Actions runtime.
    items = build_checklist(spa_count=0, auth_count=0, antibot_count=1,
                            parse_errors=0, shape={})
    assert any("proxy de país" in i for i in items)
    assert not any("VM" in i for i in items)


def test_write_report_roundtrips(tmp_path):
    report = WarmupReport(source_site="x", sampled=0, fetched=0, spa_count=0,
                          auth_count=0, antibot_count=0, fetch_errors=0,
                          parse_errors=0,
                          shape={"count": 0}, per_url=[], checklist=["ok"])
    out = tmp_path / ".scrape-warmup-report.json"
    write_report(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_site"] == "x" and data["checklist"] == ["ok"]
