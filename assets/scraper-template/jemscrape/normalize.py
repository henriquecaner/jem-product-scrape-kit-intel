import html
import re

from .canonical import CanonicalRecord

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean_text(html_text):
    if not html_text:
        return ""
    text = html.unescape(html_text)
    text = _TAG.sub(" ", text)
    return _WS.sub(" ", text).strip()


def normalize(raw, *, source_site, source_url, scraped_at, authorization_ref, raw_ref):
    breadcrumbs = list(raw.get("breadcrumbs") or [])
    description_raw = raw.get("description") or raw.get("description_raw") or ""
    rec = CanonicalRecord(
        source_site=source_site,
        source_url=source_url,
        scraped_at=scraped_at,
        authorization_ref=authorization_ref,
        product_id=raw.get("product_id") or raw.get("sku") or "",
        sku=raw.get("sku") or "",
        name=raw.get("name") or "",
        brand=raw.get("brand") or "",
        description_raw=description_raw,
        description_clean=clean_text(description_raw),
        breadcrumbs=breadcrumbs,
        division=raw.get("division") or (breadcrumbs[0] if breadcrumbs else ""),
        category_path=" > ".join(breadcrumbs),
        category_canonical="",
        images=list(raw.get("images") or []),
        specs=dict(raw.get("specs") or {}),
        prices=list(raw.get("prices") or []),
        list_price=raw.get("list_price"),
        cost_price=raw.get("cost_price"),
        variants=list(raw.get("variants") or []),
        stock=dict(raw.get("stock") or {}),
        attachments=list(raw.get("attachments") or []),
        related=list(raw.get("related") or []),
        raw_ref=raw_ref,
    )
    rec.validate()
    return rec
