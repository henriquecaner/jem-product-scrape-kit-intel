---
description: Show scrape progress — the resume cursor, the daily log, and (on Actions) the artifact/commit link.
---

Report the current scraping project's status. This is **read-only** — do not start or resume a scrape.

1. Read `state/cursor.json` (the resume checkpoint) and summarize how many URLs are done vs pending.
2. Read `docs/DAILY.md` if present for the recent run history and the last outcome.
3. On the **GitHub Actions** runtime, return the latest run's `upload-artifact` download link and the checkpoint commit, so the operator can pull the deliverable.
4. If a run is paused (token expired, warm-up not green, gate blocked), say so and point to the next action.
