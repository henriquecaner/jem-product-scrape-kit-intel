import json

import scrape_setup


def _which(present):
    return lambda n: ("/usr/bin/" + n) if n in present else None


def test_setup_ready_returns_0(capsys):
    rc = scrape_setup.main([], which=_which({"git", "gh", "python3", "playwright"}))
    assert rc == 0
    assert "READY" in capsys.readouterr().out


def test_setup_ready_with_only_optional_missing_returns_0(capsys):
    # playwright (optional) missing but all REQUIRED present -> still ready (exit 0).
    rc = scrape_setup.main([], which=_which({"git", "gh", "python3"}))
    assert rc == 0
    assert "READY" in capsys.readouterr().out


def test_setup_missing_required_returns_1_with_kit(capsys):
    rc = scrape_setup.main([], which=_which({"python3"}))   # git, gh missing
    assert rc == 1
    err = capsys.readouterr().err
    assert "winget install" in err and "NOT READY" in err


def test_setup_applies_path_fix(tmp_path):
    settings = tmp_path / "settings.json"
    rc = scrape_setup.main(
        ["--settings", str(settings)],
        which=_which({"git", "gh", "python3", "playwright"}),
        path_env={"PATH": "/opt/bin"})
    assert rc == 0
    assert json.loads(settings.read_text(encoding="utf-8"))["env"]["PATH"] == "/opt/bin"
