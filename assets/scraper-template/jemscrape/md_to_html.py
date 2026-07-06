"""Minimal Markdown->HTML for the run-plan template (spec §12). NOT a general
Markdown engine — it covers exactly the subset the scrape-run-plan skill emits:
H1/H2, unordered lists, GFM tables, bold, paragraphs. Pure stdlib so it stays
in the core; the PDF step (Chrome) lives in drivers/render_pdf.py."""
import html as _html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_STYLE = """
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:46rem;
margin:2rem auto;padding:0 1rem;color:#111;line-height:1.5}
h1{font-size:1.7rem;border-bottom:2px solid #333;padding-bottom:.3rem}
h2{font-size:1.25rem;margin-top:1.6rem}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #bbb;padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:#f2f2f2}
"""


def _inline(text):
    escaped = _html.escape(text, quote=False)
    return _BOLD.sub(r"<strong>\1</strong>", escaped)


def _split_row(line):
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def md_to_html(markdown, *, title="Run Plan"):
    lines = markdown.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("## "):
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
            i += 1
        elif stripped.startswith("# "):
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
            i += 1
        elif stripped.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
        elif stripped.startswith("|") and i + 1 < n and set(lines[i + 1].strip()) <= set("|-: "):
            header = _split_row(stripped)
            i += 2  # skip header + separator
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i].strip()))
                i += 1
            thead = "".join(f"<th>{_inline(c)}</th>" for c in header)
            body = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>")
        else:
            out.append(f"<p>{_inline(stripped)}</p>")
            i += 1
    body = "\n".join(out)
    return (f"<!doctype html>\n<html><head><meta charset=\"utf-8\">"
            f"<title>{_html.escape(title)}</title><style>{_STYLE}</style></head>"
            f"<body>\n{body}\n</body></html>\n")
