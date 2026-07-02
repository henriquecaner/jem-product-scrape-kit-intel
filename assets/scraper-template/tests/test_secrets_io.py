import stat

import pytest

from jemscrape.secrets_io import materialize_secret
from jemscrape.errors import ConfigError


def test_materialize_secret_writes_value_and_returns_path(tmp_path):
    dest = tmp_path / "sub" / ".scrape-authorization.json"
    out = materialize_secret("SEC", dest, env={"SEC": '{"target_domain":"x.com"}'})
    assert out == dest
    assert dest.read_text(encoding="utf-8") == '{"target_domain":"x.com"}'


def test_materialize_secret_sets_restrictive_perms(tmp_path):
    dest = tmp_path / "s.json"
    materialize_secret("SEC", dest, env={"SEC": "data"})
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_materialize_secret_missing_raises(tmp_path):
    with pytest.raises(ConfigError):
        materialize_secret("SEC", tmp_path / "s.json", env={})


def test_materialize_secret_blank_raises(tmp_path):
    with pytest.raises(ConfigError):
        materialize_secret("SEC", tmp_path / "s.json", env={"SEC": "   "})
