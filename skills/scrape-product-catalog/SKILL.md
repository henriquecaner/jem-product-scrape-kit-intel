---
name: scrape-product-catalog
description: The guided wizard for a new product-scraping project — walks a non-technical operator through the compliance gate, warm-up lap, run-plan, run, and export, one step at a time. Trigger on "scrape products from <site>", "get this supplier's/competitor's catalog", "start a scrape", or the /scrape-init command. Orchestrates the other scrape-* skills; never runs a full scrape without a GREEN warm-up verdict.
allowed-tools: Bash, Read, Edit, Write, Task
model: opus
---

# Scrape product catalog

This is the orchestrator for a new scraping project (spec §9). The JEM operator is non-technical, so run it as a **guided wizard**: ask one question at a time, explain each step in plain language, and confirm before each gate. Never dump all the questions at once, and never skip a gate to move faster.

Each step delegates to a focused skill; this skill is the conductor.

## Before anything: is the machine ready?

If the toolchain green check hasn't passed on this machine, send the operator to `/scrape-setup` (the `scrape-onboarding` skill) first. Do not start the wizard on a machine that can't run the engine.

## The wizard, step by step

1. **Understand the target.** Ask for the URL. Then ask, one at a time:
   - Is this authorized, and how? (public competitor / contracted supplier / our own account)
   - Does it need a specific country IP (geo-restricted)?
   - Does it need to run on a schedule, unattended?
   - Roughly how many products?
   Explain why each answer matters before asking the next.

2. **Compliance gate.** Invoke `scrape-compliance-gate`: read the site's `robots.txt`, write/validate `.scrape-authorization.json`, and apply the robots precedence matrix. This is fail-closed. If it blocks (for example, a public competitor whose robots.txt disallows the target paths), **stop and explain** — do not look for a workaround.

3. **Choose the runtime.** Based on the answers (spec §5):
   - Public + ad-hoc → **Local**.
   - Geo and/or scheduled, no login → **GitHub Actions** (proxy for geo, cron for scheduling).
   - Authenticated → **supported** (spec §5.1): set `auth_required: true` + `login_url` in `config.json`; the operator runs `auth_capture.py` locally (headed browser, they log in, the session saves to `.scrape-session.json` at 0600); for Actions, push it as the `SCRAPE_STORAGE_STATE` secret. Capture is always local — the runner never logs in. Chunk auth runs to fit inside the token's life and expect a recurring local re-capture (the daily refresh ritual, `references/auth-session.md`). Very high volume or a site that forces interactive re-login inside the token's life → VM (IT-driven fallback, not automated).
   Tell the operator which runtime you chose and why.

4. **Scaffold the project.** Copy `assets/scraper-template/` into a new `scrape-<site>/` project and write the site adapter: copy `site_adapter.py.example` to `site_adapter.py` and implement `discover`/`parse` (inspect one page to work out the product/list selectors). Use `assets/project-skeleton/.gitignore` so cache and secrets stay out of git.

5. **Warm-up lap (mandatory).** Invoke `scrape-warmup`: sample 10-50 products, detect render mode / auth / anti-bot / parse-shape, then run the two-agent green-light review (Opus 4.8 `xhigh` reviewer + Sonnet 5 advisor). Act on the verdict:
   - **VERDE** → continue.
   - **AJUSTAR/REFATORAR** → fix the parser/config, then re-run the warm-up.
   - **PEDIR AJUDA** → pause and ask the operator to do the prep (capture the login session by running `auth_capture.py` locally, enable the browser path via IT, set up a proxy), then re-run the warm-up.
   Do not continue on anything but green.

6. **Run-plan.** Invoke `scrape-run-plan`: present scope, ETA, cost, and risks (built from the warm-up's evidence). If the authorization requires approval, get the sign-off before running.

7. **Run.** Start the scrape only with a GREEN warm-up verdict and (if required) approval. Local runs `scrape.py` now. For the Actions runtime: `deploy_actions` builds the `gh secret set` commands that push the gate files as repo secrets — and, for `auth_required` projects, `actions_setup.py` also materializes the conditional `SCRAPE_STORAGE_STATE` secret. The workflow template (`assets/github-actions/scrape.yml`) runs on cron with checkpointing once placed in `.github/workflows/`. `scrape.py` re-checks the gates itself, fail-closed — the compliance gate, the warm-up verdict, and (when `auth_required`) a session preflight that exits 2 on a missing/expired session — so even a skipped wizard can't run an unauthorized, un-warmed, or un-authenticated scrape.

8. **Normalize + export.** Invoke `scrape-normalize-export`: build the canonical dataset → `exports/products.csv` + `exports/wiki/`.

9. **Audit (optional but recommended).** Hand the finished run to the `scrape-run-auditor` agent for a coverage/quality check before the data goes to the store.

## Guardrails

- **The warm-up is not skippable.** No full run without a green, unexpired, domain-matching `.scrape-warmup.json` — the runtime enforces this.
- **The compliance gate is fail-closed** and runs again at runtime; a hard block means stop, not work around.
- **Talk to the operator in their language**, in plain terms. When a gate blocks or a step needs their action, say exactly what to do next.
- **Never commit secrets** (`.scrape-authorization.json`, `.scrape-warmup.json`, `.scrape-session.json`) — they're gitignored and reconstructed from Actions secrets at runtime.

## References

- `references/execution-strategy.md` — models/efforts per step (never Haiku; Sonnet 5 economical; Opus xhigh for audit/review).
- `references/runtime-github-actions.md` — the unattended Actions runtime (secrets → gates, cron, checkpoint, artifact).
- `references/auth-session.md` — the authenticated path (local session capture, the daily token-refresh ritual, fail-closed on expiry, VM-promotion trigger).
