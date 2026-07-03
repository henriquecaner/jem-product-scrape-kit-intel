# Authenticated session: capture, refresh, promotion

How a logged-in scrape runs unattended on GitHub Actions (design spec §5.1).
The engine replays a session captured on the user's machine; the token is
refreshed by a daily ritual, not by the runner. Applies only when
`config.json` has `auth_required: true`.

## Capture is local by nature

Only the user's machine can log into the site's Chrome. `auth_capture.py`
launches headed Chromium (with the country proxy on launch when geo applies,
see `geo-proxy.md`), the user logs in, and the session is saved to
`.scrape-session.json` via Playwright's `storage_state`. The file holds live
auth cookies, so it is written `0o600` and is gitignored — never committed.
The CLI prints the estimated validity and the exact `gh secret set` command;
it never pushes the secret itself.

## Two things kept separate

- **Progress** — `state/cursor.json` lets any run resume where it stopped.
  Independent of the token.
- **Token** — the session cookie (a JWT, ~10h in the fortuslive case) expires.
  Renewed by a separate ritual with its own owner and mechanism.

`jemscrape/session.py` reads the token's validity from the captured cookies;
the cursor owns progress. The two never mix.

## Daily refresh ritual

1. Run `python auth_capture.py` locally — log in, session saved.
2. `gh secret set SCRAPE_STORAGE_STATE < .scrape-session.json`.
3. Schedule the cron to fire shortly after the daily refresh, so each run
   starts well inside the token's life. Runs are chunked (`scrape.py --limit`)
   to finish before the token expires.

On Actions, `actions_setup.py` materializes `.scrape-session.json` from the
`SCRAPE_STORAGE_STATE` secret (only when `auth_required`), fail-closed: a
missing secret aborts before any fetch.

## Mid-run expiry is fail-closed

A 401/403 during a run means the token died. `fetch()` raises
`AuthExpiredError` immediately — no retry, no backoff (retrying can't revive a
dead token and can burn the session). The runner lets it propagate;
`scrape.py` catches it, flushes the records already scraped this invocation
(so nothing done so far is lost), emits a `notify.py` error annotation, and
exits non-zero. The next run resumes from the cursor once the session is
renewed.

## Machine offline

If a scheduled run needs a fresh token and the user's machine is off, the
session in the secret is stale. The preflight detects the expired session and
aborts with an alert rather than running blind; the run resumes at the next
refresh. This is an honest limitation of local capture, not a failure mode to
engineer around.

## Promotion to VM

If the site forces an interactive re-login that can't be automated inside the
token's life (a captcha or step-up on every login), the Actions path can't
keep the session alive on its own. That's the trigger to promote the run to a
VM (IT-driven, design spec §19) — the fortuslive fallback. Volume that's too
high or continuous for Actions routes to a VM by default, not as a reaction to
a block.
