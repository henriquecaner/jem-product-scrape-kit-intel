import re
from pathlib import Path

from .cache import atomic_write

_UNSAFE = re.compile(r"[^A-Za-z0-9 ._()\-]+")
_DOTS_ONLY = re.compile(r"^\.+$")


def safe_name(name, fallback="index"):
    cleaned = _UNSAFE.sub("", name or "").strip()
    if not cleaned or _DOTS_ONLY.match(cleaned):
        return fallback
    return cleaned


def _escape_link_text(text):
    # Minimal markdown escaping for the INDEX link TEXT only -- a "]" in the
    # record name would otherwise prematurely close the "[text](url)" link.
    return text.replace("[", "\\[").replace("]", "\\]")


def render_markdown(record):
    lines = [f"# {record.name}", ""]
    meta = []
    if record.sku:
        meta.append(f"**SKU:** `{record.sku}`")
    if record.brand:
        meta.append(f"**Brand:** {record.brand}")
    if meta:
        lines += [" · ".join(meta), ""]
    if record.category_path:
        lines += [f"**Category:** {record.category_path}", ""]
    if record.images:
        lines += [f"![{safe_name(record.name)}]({record.images[0]})", ""]
    if record.description_clean:
        lines += ["## Description", record.description_clean, ""]
    if record.prices:
        # In the default (empty band_priority) path, pick_price never runs,
        # so prices[0] can be a bare scalar instead of the expected
        # {"value": ..., "band": ...} dict. Guard against that shape.
        first = record.prices[0]
        p = first if isinstance(first, dict) else {}
        band = f" _(band {p.get('band')})_" if p.get("band") else ""
        lines += ["## Pricing", f"- {p.get('value')} {p.get('currency', '')}{band}".rstrip(), ""]
    lines += [f"[Source]({record.source_url})", ""]
    return "\n".join(lines)


def write_wiki(records, wiki_dir):
    wiki_dir = Path(wiki_dir)
    wiki_root = wiki_dir.resolve()
    index = ["# Product Index", ""]
    seen = set()
    count = 0
    for rec in records:
        # Fallback must NEVER be the raw, unsanitized value: if cleaning
        # empties a breadcrumb (e.g. "/", "..", "..."), falling back to the
        # original string would reintroduce the unsafe/traversal segment.
        parts = [safe_name(c, "Uncategorized") for c in rec.breadcrumbs] or ["Uncategorized"]
        product_id_part = safe_name(rec.product_id, "product")
        base = safe_name(rec.name, product_id_part)
        rel = Path(*parts) / f"{base}.md"
        if str(rel) in seen:
            rel = Path(*parts) / f"{base}-{product_id_part}.md"
        seen.add(str(rel))
        dest = wiki_dir / rel
        # Defense-in-depth: even after sanitizing every part individually,
        # confirm the assembled path can't resolve outside wiki_dir before
        # writing anything to disk.
        if wiki_root not in dest.resolve().parents:
            raise ValueError(f"refusing to write outside wiki_dir: {rel}")
        atomic_write(dest, render_markdown(rec))
        index.append(f"- [{_escape_link_text(rec.name)}]({rel.as_posix()})")
        count += 1
    atomic_write(wiki_dir / "INDEX.md", "\n".join(index) + "\n")
    return count
