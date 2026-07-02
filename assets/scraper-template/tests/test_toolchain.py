from jemscrape.toolchain import check_tools, render_it_kit


def _which(present):
    return lambda name: ("/usr/bin/" + name) if name in present else None


def test_check_tools_all_present_ready():
    rep = check_tools(which=_which({"git", "gh", "python3", "playwright"}))
    assert rep["ready"] is True
    assert rep["missing"] == []


def test_check_tools_missing_required_not_ready():
    rep = check_tools(which=_which({"git", "python3"}))   # gh (required) missing
    assert rep["ready"] is False
    assert any(t.name == "gh" for t in rep["missing"])


def test_check_tools_missing_only_optional_still_ready():
    rep = check_tools(which=_which({"git", "gh", "python3"}))   # playwright optional
    assert rep["ready"] is True
    assert any(t.name == "playwright" for t in rep["missing"])


def test_render_it_kit_lists_winget_for_missing():
    rep = check_tools(which=_which({"python3"}))   # git, gh missing (winget) + playwright (manual)
    kit = render_it_kit(rep)
    assert "Git.Git" in kit and "GitHub.cli" in kit
    assert "winget install" in kit
    assert "Playwright" in kit    # manual note for the no-winget tool


def test_render_it_kit_empty_when_ready():
    rep = check_tools(which=_which({"git", "gh", "python3", "playwright"}))
    assert render_it_kit(rep) == ""
