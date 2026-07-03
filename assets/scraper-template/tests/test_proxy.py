import pytest

from jemscrape.proxy import proxy_dict_from_url
from jemscrape.errors import ConfigError


def test_none_and_empty_return_none():
    assert proxy_dict_from_url(None) is None
    assert proxy_dict_from_url("") is None
    assert proxy_dict_from_url("   ") is None


def test_plain_proxy_no_credentials():
    d = proxy_dict_from_url("http://gw.proxy.uk:8080")
    assert d == {"server": "http://gw.proxy.uk:8080"}


def test_proxy_with_credentials_splits_them_out():
    d = proxy_dict_from_url("http://user:pass@gw.proxy.uk:8080")
    assert d == {"server": "http://gw.proxy.uk:8080",
                 "username": "user", "password": "pass"}


def test_https_scheme_preserved():
    d = proxy_dict_from_url("https://gw.proxy.uk:443")
    assert d["server"] == "https://gw.proxy.uk:443"


def test_invalid_url_without_host_raises():
    with pytest.raises(ConfigError):
        proxy_dict_from_url("http://:8080")


def test_invalid_url_error_does_not_leak_credentials():
    with pytest.raises(ConfigError) as ei:
        proxy_dict_from_url("http://user:s3cret@:8080")
    msg = str(ei.value)
    assert "s3cret" not in msg
    assert "user:s3cret" not in msg


def test_credentials_are_percent_decoded():
    d = proxy_dict_from_url("http://u%40ser:p%40ss@host:8080")
    assert d["username"] == "u@ser"
    assert d["password"] == "p@ss"


def test_ipv6_host_is_rebracketed():
    d = proxy_dict_from_url("http://[::1]:8080")
    assert d["server"] == "http://[::1]:8080"
