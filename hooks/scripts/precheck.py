#!/usr/bin/env python3
"""PreToolUse hook (defense-in-depth, spec §8/§10): block a `git add`/`git commit`
that explicitly names a scrape secret, so a credential can't be committed by
accident during authoring in Claude Code. The REAL compliance guarantee is the
runtime gate (§10) — this is a belt on top. Parse failures allow (the .gitignore
+ runtime remain the real guards); a missing interpreter fails closed via the
shim in hooks.json."""
import json
import re
import shlex
import sys

_SECRET_MARKERS = (
    ".scrape-authorization.json",
    ".scrape-warmup.json",
    ".scrape-session.json",
    ".env",
    ".token",
    ".secret",
)
# Kept as an additional signal alongside the token-based check below: it still
# catches the plain-adjacency case cheaply, but tokens are what actually decide.
_GIT_STAGE = re.compile(r"\bgit\s+(?:add|commit)\b")


def should_block(tool_name, tool_input):
    """Return a block-reason string, or None to allow."""
    if tool_name != "Bash":
        return None
    command = (tool_input or {}).get("command", "") or ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    # shlex resolves shell quote-removal (e.g. `.scrape-authorization''.json`
    # becomes the real filename token), and tolerates flags/config options
    # between `git` and `add`/`commit` (e.g. `git -C . add`, `git -c k=v commit`)
    # that the plain adjacency regex misses.
    is_staging = (
        ("git" in tokens and ("add" in tokens or "commit" in tokens))
        or bool(_GIT_STAGE.search(command))
    )
    if not is_staging:
        return None
    lowered_command = command.lower()
    lowered_tokens = [t.lower() for t in tokens]
    for marker in _SECRET_MARKERS:
        if marker in lowered_command or any(marker in t for t in lowered_tokens):
            return (f"BLOCKED: '{marker}' looks like a scrape secret and must not be "
                    f"committed. It is reconstructed from an Actions secret at runtime "
                    f"(see the scaffold .gitignore / actions_setup.py).")
    # Residual gap (defense-in-depth, not the guarantee): `git commit -a` names
    # no file in the command, so an already-tracked secret can still slip past
    # this check. The runtime gate + .gitignore are what actually stop it.
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
