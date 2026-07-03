class ConfigError(Exception):
    """Raised when config.json is missing required fields or has bad values."""


class AuthorizationError(Exception):
    """Raised when .scrape-authorization.json is missing, invalid, or forbids the target."""


class FetchError(Exception):
    """Raised when an HTTP fetch exhausts its retries."""


class WarmupError(Exception):
    """Raised when the warm-up verdict is missing, invalid, or not green — full run blocked."""


class SessionError(Exception):
    """Raised when .scrape-session.json is missing, malformed, or has no cookies."""


class AuthExpiredError(Exception):
    """Raised when the site returns 401/403 — the session token is dead.
    Fatal to the run: not retried, not swallowed as a per-URL error."""
