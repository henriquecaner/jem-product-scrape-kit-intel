def test_package_imports_and_exposes_errors():
    import jemscrape
    from jemscrape.errors import ConfigError, AuthorizationError, FetchError

    assert isinstance(jemscrape.__version__, str)
    for exc in (ConfigError, AuthorizationError, FetchError):
        assert issubclass(exc, Exception)
