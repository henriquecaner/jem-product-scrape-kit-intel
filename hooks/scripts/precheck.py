#!/usr/bin/env python3
"""PreToolUse hook (defense-in-depth, spec §8/§10): block a `git add`/`git commit`
that explicitly names a scrape secret, so a credential can't be committed by
accident during authoring in Claude Code. The REAL compliance guarantee is the
runtime gate (§10) — this is a belt on top. Parse failures allow (the .gitignore
+ runtime remain the real guards); a missing interpreter fails closed via the
shim in hooks.json."""
import json
import re
import sys

_SECRET_MARKERS = (
    ".scrape-authorization.json",
    ".scrape-warmup.json",
    ".env",
    ".token",
    ".secret",
)
_GIT_STAGE = re.compile(r"\bgit\s+(?:add|commit)\b")


def should_block(tool_name, tool_input):
    """Return a block-reason string, or None to allow."""
    if tool_name != "Bash":
        return None
    command = (tool_input or {}).get("command", "") or ""
    if not _GIT_STAGE.search(command):
        return None
    for marker in _SECRET_MARKERS:
        if marker in command:
            return (f"BLOCKED: '{marker}' looks like a scrape secret and must not be "
                    f"committed. It is reconstructed from an Actions secret at runtime "
                    f"(see the scaffold .gitignore / actions_setup.py).")
    return None


def main(stdin=None):
    stdin = sys.stdin if stdin is None else stdin
    try:
        event = json.load(stdin)
    except (ValueError, OSError):
        return 0  # can't parse the event -> don't block authoring; runtime is the guarantee
    reason = should_block(event.get("tool_name", ""), event.get("tool_input", {}))
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
