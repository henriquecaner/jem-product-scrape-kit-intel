# Changelog

## 0.1.0

First packaged release of `jem-product-scrape-kit-intel` — a compliance-first product-scraping kit for the JEM team.

**Engine (Python 3, stdlib-only core):**
- Compliance gate — fail-closed runtime authorization (`.scrape-authorization.json`) with the robots.txt precedence matrix.
- Resilient fetch (429-aware), humanized pacing, atomic cache with a resumable cursor.
- Normalize → canonical record → CSV + wiki exports; dedup (hub-stock, price-band, variants).
- Warm-up lap (mandatory) — samples a site and detects render mode (server vs SPA/JS), auth/paywall, anti-bot/geo, and parse-shape; a fail-closed verdict gate refuses the full run without a green light.
- Browser render adapter — optional Playwright path for SPA/JS sites (`fetch_mode: browser`); Playwright stays an optional dependency in `drivers/`.
- GitHub Actions runtime — workflow template that reconstructs gate secrets, enforces the gate, checkpoints, and uploads the exports artifact.
- Onboarding — toolchain green check, IT install kit, Desktop PATH fix, and the Actions deploy helper.

**Plugin:**
- Skills: `scrape-onboarding`, `scrape-product-catalog` (guided wizard), `scrape-compliance-gate`, `scrape-warmup`, `scrape-normalize-export`, `scrape-run-plan`.
- Commands: `/scrape-setup`, `/scrape-init`, `/scrape-status`.
- Agent: `scrape-run-auditor`. Hooks: `PreToolUse` credential-to-git guard (defense-in-depth).

**Deferred:** authenticated scraping + token lifecycle (Plano 3b); LLM-assisted normalization via Batch API; PDF rendering of the run-plan.
