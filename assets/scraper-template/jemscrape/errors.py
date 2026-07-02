class ConfigError(Exception):
    """Raised when config.json is missing required fields or has bad values."""


class AuthorizationError(Exception):
    """Raised when .scrape-authorization.json is missing, invalid, or forbids the target."""


class FetchError(Exception):
    """Raised when an HTTP fetch exhausts its retries."""


class WarmupError(Exception):
    """Raised when the warm-up verdict is missing, invalid, or not green — full run blocked."""
