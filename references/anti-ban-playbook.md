# Anti-Ban Playbook

Practices that keep scraping from getting the source's account or IP banned
(design spec §18).

## Pacing floor + coffee breaks (`jemscrape/pacing.py`)

`Pacer.wait(heavy=False)` sleeps a randomized delay between requests:

- Delay is drawn uniformly from `[min_delay, max_delay]` (from `config.json`:
  `min_delay_seconds` / `max_delay_seconds`).
- `heavy=True` (e.g. a request that hits more server work) multiplies the
  delay by 1.4.
- The delay is clamped up to `rate_limit_floor_seconds` if it would otherwise
  be shorter — the floor always wins, it's a hard minimum, not a suggestion.
- Every 20-30 requests (randomized count), an extra 90-240 second "coffee
  break" is added, mimicking a human pause rather than a constant-rate bot.

`rate_limit_floor_seconds` is validated as a config field
(`jemscrape/config.py` `validate_config`) and enforced at runtime, not just
documented — a config with `min_delay_seconds` below the floor fails
validation.

## Realistic user agent

`config.json` carries a `user_agent` string (e.g. `Mozilla/5.0 (compatible;
JEMScrape/1.0; +mailto:ops@jemsystems.com)`), required and non-empty by
`validate_config`. No default browser-spoofing UA is silently substituted.

## Single-thread

The engine scrapes sequentially, one request at a time, through the `Pacer`.
No concurrent fan-out against the target site — concurrency happens across
runs/chunks (Actions cron), not within a single fetch loop.

## Business hours for authenticated targets

For sites requiring login, runs are scheduled to fall within normal business
hours for the target's operators, so authenticated traffic doesn't look like
off-hours automation. This is a scheduling/cron decision made when the
project is scaffolded, not a library-enforced constraint.

## Checkpoint / resume (`state/cursor.json`)

Every run persists progress to `state/cursor.json`. This makes runs
idempotent: an interrupted or delayed cron run resumes from the last
checkpoint instead of re-scraping from scratch or skipping ahead.
`state/cursor.json` is versioned (not gitignored) — see
`runtime-github-actions.md`.

## Dedicated low-privilege account

For authenticated targets, use a scraping account dedicated to that purpose,
with the minimum privilege needed — not a shared or admin account. Ties into
the secret lifecycle (TTL, revocation on offboarding) described in the design
spec §10.4.

## Robots.txt respected

Robots.txt status is checked and enforced against the authorization type
matrix (design spec §10.2): `public_competitor` is a hard block on
`Disallow`; `contracted_partner` and `own_account` can override only with an
explicit reference recorded in the authorization file. This is enforced at
runtime (`smoke_test.py` / the compliance gate), not just advised.
