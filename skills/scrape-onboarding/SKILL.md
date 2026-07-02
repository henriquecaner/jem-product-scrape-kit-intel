---
name: scrape-onboarding
description: First-time setup for the scraping kit on a new machine. Checks that git, gh, and python3 are installed, fixes the Claude Desktop PATH, and gates progress until everything is green. Trigger on "set up the scraping kit", "why can't it find python/git/gh", "I'm getting a command not found error", "run the setup", first-time use of this plugin, or before letting the user run /scrape-init.
allowed-tools: Bash, Read, Edit, Write
model: sonnet
---

# Scrape onboarding

This is the first thing a new user runs before touching `/scrape-init`. It has two phases: one that needs IT, and one the user does alone.

## What this actually does

It wraps a small CLI, `assets/scraper-template/scrape_setup.py`. Running it does three things, in order:

1. Checks the toolchain (`jemscrape/toolchain.py`, `check_tools`). Required: **git**, **gh** (GitHub CLI), **python3**. Optional: **Playwright**, only needed for the browser path (sites that are SPA/JS-heavy or need a login).
2. Writes the current PATH into `~/.claude/settings.json` (`jemscrape/settings_patch.py`, `patch_claude_settings`). This is the fix for the classic Claude Desktop problem where the app can't see tools that work fine in a normal terminal. It merges in without wiping out any other settings already there.
3. Prints a report and returns an exit code: **0 if ready, 1 if something required is still missing.** If something required is missing, it also prints a "kit for IT" with the exact `winget install` commands needed (`render_it_kit`).

The command:

```
python3 scrape_setup.py --settings ~/.claude/settings.json
```

Run it again any time. It's safe to re-run; it just checks and re-patches.

## Fase A - needs IT (once per machine)

If git, gh, or python3 is missing, this machine needs software installed. On Windows this needs an administrator, so a normal user account can't do it.

Steps:
1. Run `scrape_setup.py`. If it exits 1, it printed a "kit for IT" block with `winget install` commands.
2. Hand that block to IT, along with `assets/it-request/README.md` (see "What to hand IT" below).
3. Wait for IT to confirm the installs are done.
4. Re-run `scrape_setup.py`.

Skip this phase entirely if git, gh, and python3 are already installed. Go straight to Fase B.

## Fase B - the user does this alone (re-runnable)

Once the required tools are present:

1. Create or log into a GitHub account.
2. Authenticate the GitHub CLI: `gh auth login`, then confirm with `gh auth status`.
3. Run `scrape_setup.py --settings ~/.claude/settings.json`. This writes the PATH fix into Claude Desktop's settings so it stops losing track of git/gh/python3 between sessions.
4. Check the final report. It must say **READY** (exit code 0) before moving on.

If it says **NOT READY**, something required is still missing. Go back to Fase A, or if `gh auth status` isn't logged in, fix that first.

## The green check is the gate

Do not run `/scrape-init` until `scrape_setup.py` reports READY. A missing required tool is not a Fase B problem: it always means IT still needs to install something. Don't try to work around it by editing PATH by hand. Let the script write it, so the fix is recorded consistently across machines.

Playwright missing is fine. It only blocks scraping of sites that need a real browser (SPA/JS rendering or login-gated pages). Everything else works without it.

## What to hand IT

Give IT two things:
- The "kit for IT" block printed by `scrape_setup.py` when it exits 1 (exact `winget install` commands for whatever is missing).
- `assets/it-request/README.md`. It covers the same toolchain plus two things IT provisions at the org level, not per machine: a shared proxy account (only needed for geo-restricted targets) and the `ANTHROPIC_API_KEY` repo secret (only needed if LLM-assisted normalization is in use). Note in that file: the project repo must be private.

IT does not need to touch anything else. GitHub login and `gh auth` are the user's job in Fase B.

## References

- `references/windows-toolchain.md` — winget IDs, the Desktop PATH fix, and what IT installs on locked-down Windows.
