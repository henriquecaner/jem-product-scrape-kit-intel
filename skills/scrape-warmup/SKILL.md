---
name: scrape-warmup
description: Runs the MANDATORY warm-up lap (sample 10-50 products, detect render/auth/anti-bot/parse-shape) and the two-agent green-light review before any full scrape. Trigger after the compliance gate is green and before a full run, or on "warm up the scraper", "is this site scrapeable", "test before running", "re-warm-up after fixing the parser". Fail-closed: the full run refuses to start without a GREEN verdict.
allowed-tools: Bash, Read, Write, Task
model: opus
---

# Scrape warmup

This runs the mandatory warm-up lap (spec §9.1) and the green-light review that decides whether a full scrape is allowed to start. It runs after the compliance gate (`scrape-compliance-gate`, which checks robots.txt and `.scrape-authorization.json`) and before the run-plan. Skipping it is not an option: `scrape.py` checks for a green verdict and refuses to run without one.

## What this actually wraps

- `assets/scraper-template/warmup.py` — the CLI. Runs the compliance gate first (`preflight`, fail-closed), then samples the site, then writes a recon report. Flags: `--sample <path to JSON list of URLs>`, `--config`, `--authz`, `--out`, `--render {http,browser}`.
- `assets/scraper-template/jemscrape/recon.py` — `run_warmup` fetches each sample URL (dependency-injected `probe_fn`/`parse_fn`), runs the four detectors on it, and aggregates into a `WarmupReport`: `sampled`, `fetched`, `spa_count`, `auth_count`, `antibot_count`, `fetch_errors`, `parse_errors`, `shape`, `per_url`, `checklist`.
- `assets/scraper-template/jemscrape/signals.py` — the four detectors:
  - **render** — server-rendered vs SPA/JS-only (empty HTML shell, `id="root"`/`id="app"`/framework markers, low visible-text ratio).
  - **auth/paywall** — login redirect, 401/403, password fields, "sign in to see price" style body markers.
  - **anti-bot/geo** — Cloudflare challenge markers, 429s, geo-block body text.
  - **parse-shape** — runs `normalize` on whatever parsed and measures field coverage (name/SKU/price/image/breadcrumb), price bands, variant ID collisions.
- `assets/scraper-template/jemscrape/warmup_gate.py` — `.scrape-warmup.json` verdict schema and `validate_warmup` (fail-closed: wrong verdict, wrong domain, missing tz, or expired all raise). `scrape.py`'s `require_warmup` calls this before any full run.

## Step 1 — run the warm-up lap

Sample 10-50 product URLs at random from the allowed `scope` (sitemap or category listing), save them as a JSON list, and run:

```
python3 warmup.py --sample sample_urls.json
```

Add `--render browser` once Playwright is installed, for sites that turn out to be SPA/JS-heavy or need a login session. Without it, `warmup.py` uses the plain HTTP path by default.

This prints a summary line (`sampled=… fetched=… spa=… auth=… antibot=… parse_errors=…`) and an **operator-prep checklist** built from whatever the sample actually showed, not a generic list. Examples of what shows up:

- "Site renderiza via JS (SPA): habilite o navegador/Playwright — o fetch HTTP puro não enxerga produto."
- "Login/paywall detectado: capture a sessão (storage_state) e logue no site antes do run."
- "Anti-bot/geo detectado: configure proxy de país no runtime GitHub Actions."
- "N página(s) falharam ao parsear — ajuste o parser antes do run."
- "Cobertura de preço < 50%: confirme se o preço exige login ou ajuste o parser."

The full report lands at `.scrape-warmup-report.json` (default `--out`). That file is the input to step 2.

If the compliance gate isn't green, `warmup.py` exits 2 before touching the network — it will not sample a site without a valid `.scrape-authorization.json`.

## Step 2 — green-light review (two agents, mandatory)

Dispatch a review of the recon report with two agents, fixed roles:

- **Reviewer: Opus 4.8, effort `xhigh`.** Reads the report and decides the verdict.
- **Advisor: Sonnet 5.** Raises hypotheses and risks for the reviewer to weigh; does not decide.

Never substitute Haiku for either role.

The verdict is exactly one of three:

| Verdict | When | What happens next |
|---|---|---|
| **VERDE** | Patterns are consistent, field coverage is sufficient, nothing blocking | Proceed to the run-plan, then the full run |
| **AJUSTAR / REFATORAR** | Parser, selectors, or config need changes (drift, low coverage, a key field missing) | Fix it, then re-run the warm-up lap |
| **PEDIR AJUDA** | Operator action needed — log in, install the Chrome extension or Playwright (via IT), set up a proxy — or a human call (ambiguous robots.txt, ToS) | Pause and ask; re-run the warm-up lap after the prep is done |

Re-warm-up is not optional after AJUSTAR or PEDIR AJUDA. On a SPA, for instance, the first HTTP-only pass can't measure parse shape at all; the numbers only mean something once the browser path is in place.

## Step 3 — on VERDE, write the gate file

Write `.scrape-warmup.json` with:

- `verdict`: `"green"`
- `target_domain`: must match the host of the URL the full run will hit
- `expires_at`: ISO-8601 with a timezone offset (naive datetimes are rejected)
- `report_sha256`: hash of the recon report this verdict is based on, for traceability
- `reviewer`: `"Opus 4.8 xhigh"`
- `advisor`: `"Sonnet 5"`

This file is **gitignored** — it never gets committed, same treatment as `.scrape-authorization.json`.

## The hard rule

No full run without a green, unexpired, domain-matching verdict. `scrape.py`'s `require_warmup` calls `load_warmup_verdict` and `validate_warmup` before it does anything else, and it's fail-closed: missing file, wrong verdict, domain mismatch, missing timezone, or an expired `expires_at` all abort the run with a non-zero exit before a single URL is fetched. Same fail-closed design as the compliance gate: auto-declared, but enforced at runtime, not just checked by a human once.

## References

- `references/execution-strategy.md` — the 2-agent review roles (Opus 4.8 xhigh reviewer + Sonnet 5 advisor; never Haiku).
