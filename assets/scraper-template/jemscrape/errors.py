class ConfigError(Exception):
    """Raised when config.json is missing required fields or has bad values."""


class AuthorizationError(Exception):
    """Raised when .scrape-authorization.json is missing, invalid, or forbids the target."""


class FetchError(Exception):
    """Raised when an HTTP fetch exhausts its retries."""
