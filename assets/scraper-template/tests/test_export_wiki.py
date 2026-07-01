from jemscrape.export_wiki import write_wiki, safe_name, render_markdown
from jemscrape.canonical import CanonicalRecord


def _rec(pid, name, crumbs):
    return CanonicalRecord(
        source_site="e", source_url="https://e/p/" + pid, scraped_at="t", authorization_ref="a",
        product_id=pid, sku=pid, name=name, brand="Acme", description_raw="", description_clean="Desc.",
        breadcrumbs=crumbs, division=crumbs[0] if crumbs else "", category_path=" > ".join(crumbs),
        images=["https://e/i/" + pid + ".jpg"],
        specs={}, prices=[{"value": 9.5, "band": "PLE-J015", "source": "jem_band"}],
        list_price=None, cost_price=None, variants=[], stock={"total": 3},
        attachments=[], related=[], raw_ref="",
    )


def test_safe_name_strips_unsafe_chars():
    s = safe_name("1kg Powder / Extinguisher (APS1)")
    assert "/" not in s and s


def test_render_markdown_has_name_and_link():
    md = render_markdown(_rec("A1", "Widget", ["Fire", "Detectors"]))
    assert "# Widget" in md
    assert "https://e/p/A1" in md
    assert "PLE-J015" in md


def test_write_wiki_creates_files_under_breadcrumbs_and_index(tmp_path):
    wiki = tmp_path / "wiki"
    n = write_wiki([_rec("A1", "Widget", ["Fire", "Detectors"]),
                    _rec("A2", "Gadget", ["Fire"])], wiki)
    assert n == 2
    assert (wiki / "Fire" / "Detectors").is_dir()
    md_files = list(wiki.rglob("*.md"))
    names = {p.name for p in md_files}
    assert "INDEX.md" in names
    assert any(p.match("Fire/Detectors/*.md") for p in md_files)
    index = (wiki / "INDEX.md").read_text(encoding="utf-8")
    assert "Widget" in index and "Gadget" in index


def test_write_wiki_disambiguates_path_collision(tmp_path):
    wiki = tmp_path / "wiki"
    # same name + same breadcrumbs -> would collide; must not overwrite
    n = write_wiki([_rec("A1", "Widget", ["Fire"]), _rec("A2", "Widget", ["Fire"])], wiki)
    assert n == 2
    md_files = [p for p in wiki.rglob("*.md") if p.name != "INDEX.md"]
    assert len(md_files) == 2  # both written, not overwritten


def test_safe_name_rejects_dot_only_segments():
    # A cleaned value made only of dots (".", "..", "...") must not survive
    # unchanged -- " .. " is a legal path-traversal segment on every OS.
    assert safe_name("..", "fallback") == "fallback"
    assert safe_name("...", "fallback") == "fallback"
    assert safe_name(".", "fallback") == "fallback"


def test_safe_name_fallback_used_verbatim_when_cleaning_empties_input():
    # safe_name returns the caller-supplied fallback as-is when cleaning
    # empties the input. It is the CALLER's job (write_wiki) to never pass
    # the raw unsafe value back in as its own fallback -- see
    # test_write_wiki_*_stays_inside_wiki_dir below for that guarantee.
    assert safe_name("/", "safe-fallback") == "safe-fallback"
    assert safe_name("..", "safe-fallback") == "safe-fallback"


def test_write_wiki_traversal_breadcrumb_stays_inside_wiki_dir(tmp_path):
    wiki = tmp_path / "safe_area" / "wiki"
    n = write_wiki([_rec("A1", "Evil", ["..", "..", "escaped"])], wiki)
    assert n == 1
    # Nothing may be written outside wiki_dir's parent-of-parent.
    assert not (tmp_path / "escaped").exists()
    md_files = [p for p in wiki.rglob("*.md") if p.name != "INDEX.md"]
    assert len(md_files) == 1
    assert wiki.resolve() in md_files[0].resolve().parents


def test_write_wiki_absolute_path_breadcrumb_stays_inside_wiki_dir(tmp_path):
    wiki = tmp_path / "safe_area" / "wiki"
    n = write_wiki([_rec("A1", "Evil", ["/", "etc"])], wiki)
    assert n == 1
    md_files = [p for p in wiki.rglob("*.md") if p.name != "INDEX.md"]
    assert len(md_files) == 1
    assert wiki.resolve() in md_files[0].resolve().parents
