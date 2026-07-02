import re

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<script\b.*?</script>", re.I | re.S)
_WS = re.compile(r"\s+")

_SPA_MARKERS = (
    'id="root"', "id='root'", 'id="app"', "id='app'",
    "<app-root", "ng-app", "__next_data__", "window.__nuxt__",
    "data-reactroot", "window.__initial_state__",
)


def detect_render(body):
    body = body or ""
    low = body.lower()
    without_scripts = _SCRIPT.sub(" ", body)
    visible = _WS.sub(" ", _TAG.sub(" ", without_scripts)).strip()
    text_len = len(visible)
    markers = [m for m in _SPA_MARKERS if m in low]
    total = max(len(body), 1)
    script_len = sum(len(m.group(0)) for m in _SCRIPT.finditer(body))
    script_ratio = script_len / total
    spa = bool(markers) and text_len < 500
    if not spa and text_len < 200 and script_ratio > 0.5:
        spa = True
    return {
        "mode": "spa" if spa else "server",
        "text_len": text_len,
        "script_ratio": round(script_ratio, 3),
        "markers": markers,
    }


_LOGIN_PATH = re.compile(r"/(login|signin|sign-in|account|myaccount|auth)(/|$|\?)", re.I)
_LOGIN_BODY = (
    "sign in to see price", "log in to view", "please sign in",
    "login required", "member price", 'type="password"',
)


def detect_auth(probe):
    signals = []
    if probe.status in (401, 403):
        signals.append(f"status {probe.status}")
    if _LOGIN_PATH.search(probe.final_url or ""):
        signals.append(f"auth URL: {probe.final_url}")
    low = (probe.body or "").lower()
    for marker in _LOGIN_BODY:
        if marker in low:
            signals.append(f"body marker: {marker!r}")
    return {"auth_required": bool(signals), "signals": signals}


_CF_BODY = (
    "just a moment", "attention required", "cf-chl",
    "checking your browser", "cf-browser-verification",
)
_GEO_BODY = (
    "not available in your country", "access denied",
    "blocked in your region", "not available in your region",
)


def detect_antibot(probe):
    signals = []
    kind = None
    if probe.status == 429:
        signals.append("status 429 (rate limited)")
        kind = "rate"
    if "cf-ray" in probe.headers or "cf-mitigated" in probe.headers:
        signals.append("cloudflare header (cf-ray)")
        kind = kind or "cloudflare"
    low = (probe.body or "").lower()
    for marker in _CF_BODY:
        if marker in low:
            signals.append(f"cloudflare body: {marker!r}")
            kind = kind or "cloudflare"
            break
    for marker in _GEO_BODY:
        if marker in low:
            signals.append(f"geo-block body: {marker!r}")
            kind = kind or "geo"
            break
    return {"blocked": bool(signals), "kind": kind, "signals": signals}


def analyze_shape(records):
    n = len(records)
    if n == 0:
        return {"count": 0, "coverage": {}, "price_bands": [],
                "variant_collisions": 0, "stock_by_location": 0}

    def frac(pred):
        return round(sum(1 for r in records if pred(r)) / n, 3)

    coverage = {
        "name": frac(lambda r: bool(r.name)),
        "sku": frac(lambda r: bool(r.sku)),
        "product_id": frac(lambda r: bool(r.product_id)),
        "price": frac(lambda r: bool(r.prices)),
        "image": frac(lambda r: bool(r.images)),
        "breadcrumbs": frac(lambda r: bool(r.breadcrumbs)),
    }
    bands = sorted({p.get("band") for r in records for p in r.prices
                    if isinstance(p, dict) and p.get("band")})
    seen = {}
    for r in records:
        seen[r.product_id] = seen.get(r.product_id, 0) + 1
    collisions = sum(1 for count in seen.values() if count > 1)
    stock_by_loc = sum(1 for r in records if r.stock.get("by_location"))
    return {
        "count": n,
        "coverage": coverage,
        "price_bands": bands,
        "variant_collisions": collisions,
        "stock_by_location": stock_by_loc,
    }
