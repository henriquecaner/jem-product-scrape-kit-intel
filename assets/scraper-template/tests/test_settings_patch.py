import json

from jemscrape.settings_patch import patch_claude_settings


def test_patch_creates_file_with_env(tmp_path):
    p = tmp_path / "settings.json"
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["env"]["PATH"] == "/opt/bin"
    assert json.loads(p.read_text(encoding="utf-8"))["env"]["PATH"] == "/opt/bin"


def test_patch_preserves_existing_keys_and_env(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"model": "opus", "env": {"FOO": "bar"}}), encoding="utf-8")
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["model"] == "opus"
    assert out["env"]["FOO"] == "bar"
    assert out["env"]["PATH"] == "/opt/bin"


def test_patch_survives_corrupt_settings(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json", encoding="utf-8")
    out = patch_claude_settings(p, env={"PATH": "/opt/bin"})
    assert out["env"]["PATH"] == "/opt/bin"


def test_patch_does_not_clobber_existing_path_with_empty(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"PATH": "/usr/bin:/opt/good/bin"}}), encoding="utf-8")
    out = patch_claude_settings(p, env={"PATH": ""})
    assert out["env"]["PATH"] == "/usr/bin:/opt/good/bin"
    assert json.loads(p.read_text(encoding="utf-8"))["env"]["PATH"] == "/usr/bin:/opt/good/bin"
