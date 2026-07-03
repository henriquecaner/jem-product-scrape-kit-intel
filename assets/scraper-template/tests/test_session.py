from jemscrape.errors import SessionError, AuthExpiredError


def test_session_and_auth_exceptions_exist_and_are_exceptions():
    assert issubclass(SessionError, Exception)
    assert issubclass(AuthExpiredError, Exception)
