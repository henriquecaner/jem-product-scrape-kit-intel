"""Emit a GitHub Actions annotation on scrape failure/warning. Pure formatting
plus a thin emit; opening a repo issue via gh is an onboarding/driver concern."""
import argparse
import sys

_LEVELS = {"error": "::error::", "warning": "::warning::", "notice": "::notice::"}


def format_notification(kind, message):
    prefix = _LEVELS.get(kind, "::notice::")
    return f"{prefix}[scrape] {message}"


def emit(kind, message, *, stream=None):
    stream = sys.stdout if stream is None else stream
    print(format_notification(kind, message), file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Emit a GitHub Actions annotation")
    parser.add_argument("--kind", choices=sorted(_LEVELS), default="error")
    parser.add_argument("--message", required=True)
    args = parser.parse_args(argv)
    emit(args.kind, args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
