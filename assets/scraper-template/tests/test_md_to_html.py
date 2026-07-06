from jemscrape.md_to_html import md_to_html


def test_headers_and_paragraph():
    html = md_to_html("# Title\n\nHello world")
    assert "<h1>Title</h1>" in html
    assert "<p>Hello world</p>" in html
    assert html.lstrip().lower().startswith("<!doctype html>")


def test_list_and_bold():
    html = md_to_html("- one\n- **two**")
    assert "<li>one</li>" in html
    assert "<li>one</li>" in html and "<strong>two</strong>" in html
    assert "<ul>" in html


def test_table():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    html = md_to_html(md)
    assert "<table>" in html
    assert "<th>A</th>" in html and "<td>1</td>" in html


def test_escapes_html_in_content():
    html = md_to_html("A <script> & B")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html
