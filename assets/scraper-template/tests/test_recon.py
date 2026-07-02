import json

from jemscrape.recon import run_warmup, write_report, WarmupReport
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
    mapping = {
        "https://x/spa": Probe(status=200, headers={}, body=SPA_BODY, final_url="https://x/spa"),
        "https://x/server": Probe(status=200, headers={}, body=SERVER_BODY, final_url="https://x/server"),
        "https://x/auth": Probe(status=403, headers={}, body="", final_url="https://x/account/login"),
        "https://x/dead": FetchError("boom"),
    }
    report = run_warmup(
        list(mapping.keys()), probe_fn=_fake_probe(mapping), parse_fn=_parse,
        source_site="x", scraped_at="t", authorization_ref="a")
    assert report.sampled == 4
    assert report.fetched == 3          # dead one raised
    assert report.fetch_errors == 1
    assert report.spa_count == 1
    assert report.auth_count == 1
    assert report.shape["count"] == 1   # only the server page parsed+normalized
    assert any("SPA" in c or "JS" in c for c in report.checklist)


def test_write_report_roundtrips(tmp_path):
    report = WarmupReport(source_site="x", sampled=0, fetched=0, spa_count=0,
                          auth_count=0, antibot_count=0, fetch_errors=0,
                          shape={"count": 0}, per_url=[], checklist=["ok"])
    out = tmp_path / ".scrape-warmup-report.json"
    write_report(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source_site"] == "x" and data["checklist"] == ["ok"]
