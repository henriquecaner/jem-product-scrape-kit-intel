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
