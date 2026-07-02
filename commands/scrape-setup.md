---
description: First-time setup — check the toolchain (git, gh, Python, Playwright), fix the Desktop PATH, and generate an IT install kit for anything missing.
---

Run the first-time onboarding for the JEM scraping kit.

Use the **scrape-onboarding** skill:

1. Run the toolchain green check (`assets/scraper-template/scrape_setup.py`) to detect git, GitHub CLI (`gh`), Python 3, and Playwright.
2. Apply the Desktop PATH fix to `~/.claude/settings.json` (so `python3`/`gh` resolve when Claude Code is opened from the Dock/Finder).
3. If anything **required** is missing, print the IT kit (winget commands from `render_it_kit`) for the user to hand to IT, and stop — do not proceed.
4. When the green check passes, tell the user they can run `/scrape-init`.

This command is safe to re-run.
