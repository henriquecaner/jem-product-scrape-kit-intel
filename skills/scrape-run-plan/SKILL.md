---
name: scrape-run-plan
description: Generates the pre-run briefing (scope, ETA, cost, risks, approval) before a full scrape runs. Trigger after the warm-up lap comes back green and before the full run starts, or when the operator asks "how long will this take", "how much will this cost", "run plan", or "get approval".
allowed-tools: Bash, Read, Write
model: sonnet
---

# Scrape run plan

This produces the briefing the operator reads before the full scrape starts — and, for sensitive projects, the document they sign off on. It runs only after the warm-up lap (`scrape-warmup`) has a **green** verdict. It does not guess: every number in the briefing comes from the warm-up's recon report, not from assumptions made before the site was ever touched.

## When to run this

After warm-up, before the full run. Never before warm-up — there is no evidence yet to build a plan on. If the warm-up verdict is `adjust` or `ask`, stop and send the operator back to `scrape-warmup`; do not draft a briefing against a site that has not been given the green light.

## What this wraps

- The warm-up's recon report (`jemscrape/recon.py`, `WarmupReport`) — sample size, fetched count, render/auth/antibot signals, parse coverage (`shape`).
- The warm-up verdict (`jemscrape/warmup_gate.py`, `WarmupVerdict`) — must be `green`, tied to a specific recon report by `report_sha256`, and not expired.
- The authorization record (`jemscrape/authz.py`, `Authorization`) — `target_domain`, `rate_limit_floor_seconds`, `requires_approval`, `scope`.
- `config.json` — `runtime` (`local` or the Actions path) and `fetch_mode` (`http` or `browser`).

This skill does not scrape, fetch, or normalize anything. It reads the evidence these components already produced and writes it up.

## Building the briefing

Read the recon report and the authorization record, then fill in each section below. If a number can't be traced back to one of those files, don't put it in the briefing — flag it as unknown instead of estimating.

### 1. Scope

State the target site, the categories or brands in scope (from `authorization.scope`), the estimated total URL count (extrapolated from the warm-up's discovery — sitemap or category listing, not the 10–50 sampled), the chosen runtime (Local or GitHub Actions), and the fetch mode (`http` or `browser`, from `config.json`).

### 2. ETA

Estimate wall-clock time as total URL count times the rate-limit floor (`rate_limit_floor_seconds` from the authorization record). State this assumption plainly: pacing is humanized and single-threaded by design (§10, §18 of the design spec — this is what keeps the account from getting banned), so the floor dominates the runtime, not bandwidth or parsing speed. Do not model concurrency or throughput gains that the pacer does not actually allow.

### 3. Cost

State the token/cost estimate for any LLM-based normalization. As of this plan, v1 normalization is deterministic code — no LLM calls, so the cost here is effectively zero. Note that the Batch API path (roughly half the per-token cost) only applies once LLM-assisted normalization is added on top of the deterministic pipeline, and only on the GitHub Actions runtime with an `ANTHROPIC_API_KEY` configured — the Local runtime runs under the Claude Code subscription and does not route through Batch. Don't project a cost for a feature that isn't built.

### 4. Risks and mitigations

Pull risks straight from the warm-up's signals and the checklist it generated, plus the compliance posture:

| Signal from warm-up | Risk | Mitigation |
|---|---|---|
| SPA / JS-rendered pages | HTTP-only fetch sees no product data | Switch `fetch_mode` to `browser` (Playwright) |
| Login / paywall detected | Content behind auth is invisible to the scrape | Capture a login session locally (`auth_capture.py` → `.scrape-session.json`), set `auth_required: true` + `login_url`, and for Actions push `SCRAPE_STORAGE_STATE`; then re-run the warm-up authenticated |
| Auth token expires mid-run | The run aborts fail-closed (`AuthExpiredError`) once the session dies | Chunk the run to fit inside the token's life; recapture the session before scheduled runs (the daily refresh ritual, `references/auth-session.md`) |
| Anti-bot challenge / geo-block | Requests get blocked or throttled | Route through a country proxy on the GitHub Actions runtime (automatic VM promotion is not built — it's a manual, IT-driven fallback) |
| Low field coverage (name/SKU/price/image) | Exports will have gaps | Fix the parser and re-run the warm-up before proceeding |
| `robots_status: disallowed` | Compliance gate blocks the run | Apply the authorization-type precedence matrix (§10.2) — hard block for `public_competitor`; override only with `robots_override_ref` for `contracted_partner`; `own_account` is allowed without one |

Only list a risk if the warm-up or the authorization record actually surfaced it. A clean warm-up gets a short risk section, not a padded one.

### 5. Authorization and sign-off

Reference the `.scrape-authorization.json` that already gates this target: `authorization_type`, `approver`, `expires_at`, `scope`. State plainly whether it is still valid for the run window.

If `requires_approval` is `true` in that record, this briefing is the document that gets approved: after the operator or the designated approver reviews it, write `.scrape-approval.json` with a hash of this run-plan and the approver's identity. Note this as a step this skill performs when asked, not as something the runtime already checks — the compliance code (`scrape.py` preflight) currently enforces the authorization record itself; the approval marker is a project-level gate this skill and the operator maintain, not (yet) something `scrape.py` verifies automatically.

## Output

Render the briefing as a Markdown file (for example `docs/run-plan.md` in the project scaffold). This is the v1 deliverable — plain, readable, works everywhere without extra tooling.

A PDF render is a documented future enhancement, not something this skill does today. The design spec (§12) describes a future `render_pdf.py` that would discover a local Chrome binary and fall back to HTML/Markdown if it can't find one, specifically so an approval step never blocks on missing software. Until that driver exists, Markdown is the only output format — do not tell the operator a PDF is available.

## Briefing template

```
# Run Plan — <site>

## 1. Scope
- Target: <domain>
- Categories/brands: <from authorization.scope>
- Estimated URLs: <count, from warm-up discovery>
- Runtime: Local | GitHub Actions
- Fetch mode: http | browser

## 2. ETA
- Estimated total time: <URL count x rate_limit_floor_seconds>
- Assumption: single-threaded, humanized pacing — the rate floor sets the pace, not bandwidth.

## 3. Cost
- LLM normalization cost: <$0 today — v1 normalize is deterministic>
- Batch API note: <applies only if/when LLM-assisted normalization is added, Actions runtime only>

## 4. Risks -> Mitigations
- <risk from warm-up signal> -> <mitigation>
- ...

## 5. Authorization and sign-off
- Authorization: <type, approver, expires_at>
- Approval required: yes/no
- If yes: .scrape-approval.json <pending | written, with hash>
```

## References

- `references/estimation.md` — how ETA and cost are estimated (URL count × rate-limit floor; LLM cost ~zero for v1).
- `references/execution-strategy.md` — cost levers (Batch only on Actions; deterministic parsing).
