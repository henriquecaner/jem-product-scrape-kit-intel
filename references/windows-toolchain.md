# Windows Toolchain

Onboarding for non-technical Windows users, where software installation
depends on IT (design spec §6, §12, §19).

## Two-phase onboarding

**Phase A (once per machine, needs IT).** Detection + a generated "IT kit":
a document with silent winget install commands for whatever's missing.
**Phase B (user does alone, re-runnable).** GitHub login, PATH fix, green
check that gates `/scrape-init`.

## Toolchain registry (`jemscrape/toolchain.py`)

`TOOLS` lists each tool with its executable name, label, winget ID, why it's
needed, and whether it's required:

| Tool | winget ID | Why | Required |
|---|---|---|---|
| Git | `Git.Git` | version control + resume checkpoints | yes |
| GitHub CLI (`gh`) | `GitHub.cli` | `gh secret set` / repo ops (Actions runtime) | yes |
| Python 3 | `Python.Python.3.12` | runs the scraper engine | yes |
| Playwright | (none — pip, not winget) | browser render path for SPA/JS sites | no (optional) |

`check_tools(*, which)` probes each tool via a `which`-style lookup and
returns `{ready, present, missing}` — `ready` is true only when every
**required** tool is present; Playwright missing doesn't block readiness.

Playwright install is two commands, not winget: `pip install playwright &&
playwright install chromium`. It may still need IT if the Chromium binary
download is blocked by network policy.

## IT kit rendering

`render_it_kit(report)` turns a missing-tools report into a markdown doc:
silent winget install lines for anything with a winget ID, plus a manual
steps list for anything without one (Playwright). This is the artifact IT
runs once, as administrator, in PowerShell. The template lives at
`assets/it-request/README.md` and also documents org-level, not per-user,
provisioning: the shared proxy account, `ANTHROPIC_API_KEY`, and GCP (VM
fallback only).

## Desktop PATH fix

The Claude Code Desktop app doesn't always inherit the shell's `PATH`, so
`python3`/`gh`/`playwright` can appear "not found" even when installed.
`jemscrape/settings_patch.py` `patch_claude_settings(path, *, env)` merges an
`env` dict (typically `{"PATH": <resolved PATH>}`) into `~/.claude/settings.json`
without clobbering other keys, using an atomic write. This is applied by the
setup CLI, not left as a manual step for the user.

## `scrape_setup.py` (backs `/scrape-setup`)

Runs `check_tools`, prints a present/missing report, optionally writes the
PATH fix via `--settings <path to settings.json>`, prints the IT kit to
stderr if anything required is missing, and returns non-zero when not ready.
This is the green check that gates `/scrape-init` — exit 0 only when every
required tool is present.

## `gh` CLI

Required specifically because `gh secret set` is how gate secrets and
(optionally) `HTTPS_PROXY` / `ANTHROPIC_API_KEY` get pushed to a generated
project's Actions secrets (see `drivers/deploy_actions.py`, which builds `gh
secret set <NAME>` commands piping the secret value via stdin — never on
argv, to avoid leaking it into process listings).
