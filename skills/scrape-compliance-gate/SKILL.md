---
name: scrape-compliance-gate
description: Writes and validates the .scrape-authorization.json that gates every scrape run — checks robots.txt, applies the public_competitor/contracted_partner/own_account precedence matrix, and confirms the fail-closed preflight gate passes before any fetch. Trigger before starting a new scrape target, when the user asks "is this allowed", "check robots", "can we scrape this site", or when config.json references a domain with no authorization file yet.
allowed-tools: Bash, Read, Write, WebFetch
model: sonnet
---

# Scrape Compliance Gate

Authorization comes before scraping, not after. This skill writes the authorization record and confirms the runtime gate accepts it. It does not scrape anything itself.

## What this wraps

- `assets/scraper-template/jemscrape/authz.py` — `Authorization` dataclass, `load_authorization()`, `validate(auth, target_url, now)`. Fail-closed: any missing field, expired date, domain mismatch, or robots violation raises `AuthorizationError`.
- `assets/scraper-template/jemscrape/config.py` — `load_config()` / `validate_config()`, read alongside the authorization during preflight.
- `assets/scraper-template/scrape.py` — `preflight(config_path, authz_path, now)`, the single runtime gate. `main()` calls it before touching the network and exits non-zero on failure.
- `assets/scraper-template/smoke_test.py` — calls `preflight()` directly. Run it to check the gate without running a scrape.

## Step 1 — Read the target's robots.txt

Fetch `https://<target_domain>/robots.txt` with WebFetch. Determine, for the paths this project intends to scrape:

- **allowed** — no matching `Disallow` for the relevant user-agent / paths.
- **disallowed** — a matching `Disallow` blocks the paths in scope.

If robots.txt is missing or returns a non-200, treat that as `allowed` but say so explicitly to the user — don't silently assume.

## Step 2 — Write `.scrape-authorization.json`

Location: project root, next to `config.json` (path used by `scrape.py` is `HERE / ".scrape-authorization.json"`).

This file is a secret. It is gitignored by the project scaffold (`/assets/project-skeleton/.gitignore` blocks it). **Never commit it, never print its full contents into a location that gets committed.**

Schema (all fields required, matching `Authorization.__annotations__` in `authz.py`):

| field | type | notes |
|---|---|---|
| `target_domain` | string | exact host, no scheme/path. Must equal the host of the URLs `scrape.py` builds from `config.json`'s `target_domain`, or validation rejects the run. |
| `authorization_type` | string | one of `public_competitor`, `contracted_partner`, `own_account`. |
| `approver` | string | who approved this. Required non-empty. |
| `approved_at` | ISO-8601 datetime, with timezone offset | when approval was granted. |
| `expires_at` | ISO-8601 datetime, with timezone offset | hard expiry. A naive datetime (no offset) is rejected, not just a past date. |
| `rate_limit_floor_seconds` | number > 0 | minimum delay between requests; matches `config.json`'s `rate_limit_floor_seconds` field. |
| `robots_status` | string | `allowed` or `disallowed` — from Step 1. |
| `robots_override_ref` | string or null | reference (e.g. contract/MSA id) justifying a scrape despite `disallowed`. Required (non-blank) when `authorization_type` is `contracted_partner` and `robots_status` is `disallowed`. |
| `requires_approval` | bool | recorded and loaded today; not yet enforced by `validate()`. A future run-plan approval layer (`.scrape-approval.json`) will check this — treat it as declared intent, not an active gate. |
| `scope` | string | what may be captured — the consent boundary. Same status as `requires_approval`: recorded now, not yet enforced by code. |

Example:

```json
{
  "target_domain": "example.com",
  "authorization_type": "contracted_partner",
  "approver": "henrique.caner@jemsystems.com",
  "approved_at": "2026-07-01T09:00:00+00:00",
  "expires_at": "2026-07-08T09:00:00+00:00",
  "rate_limit_floor_seconds": 2.5,
  "robots_status": "disallowed",
  "robots_override_ref": "MSA-2026-014",
  "requires_approval": false,
  "scope": "product catalog pages only"
}
```

## Step 3 — Robots precedence matrix

`validate()` applies this before anything else runs:

| `authorization_type` | `robots_status: disallowed` |
|---|---|
| `public_competitor` | **Hard block.** `validate()` raises `AuthorizationError`. No override field exists for this type — do not scrape. |
| `contracted_partner` | Allowed **only** with a non-blank `robots_override_ref` pointing at the contract that authorizes the override. Blank or whitespace-only refs are rejected the same as a missing one. |
| `own_account` | Allowed. It's the org's own site; no override reference needed. |

`robots_status: allowed` passes for all three types. There is no path that lets `public_competitor` proceed against a `disallowed` robots.txt — if the target disallows the paths in scope, stop and tell the user, don't look for a workaround.

## Step 4 — Verify with the gate

Don't just write the file — confirm the runtime accepts it:

```bash
python smoke_test.py
```

This calls `preflight(config.json, .scrape-authorization.json, now)`, which loads and validates both files together (domain match, expiry, robots precedence). `[smoke] OK` on stdout means the gate passes; `[smoke] FAIL: <reason>` on stderr with a non-zero exit means it doesn't — fix the authorization file, not the check.

## Why this can't be skipped

`scrape.py main()` calls the identical `preflight()` before any fetch happens, every run, local or in GitHub Actions. There is no flag to bypass it and no code path that scrapes without a fresh, passing authorization. The gate is fail-closed: a missing file, an expired date, a domain mismatch, or a robots violation aborts the run with a non-zero exit before a single request goes out.

The gate is auto-declaration by design — it trusts whoever writes the JSON, matching JEM's internal threat model. It does not verify the approver's identity or check external records. Projects handling more sensitive targets add a run-plan approval step (`.scrape-approval.json`, tracked in a later plan) on top of this gate; that layer hardens the process, it doesn't replace this one.
