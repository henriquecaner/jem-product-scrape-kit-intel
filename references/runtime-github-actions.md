# Runtime: GitHub Actions

The sweet-spot runtime for public or authenticated, geo/scheduled scraping
with no interactive human present (design spec §5, §5.1, §5.3). Template:
`assets/github-actions/scrape.yml`.

## Secrets -> gate files

The compliance gate files (`.scrape-authorization.json`, `.scrape-warmup.json`)
are gitignored — they're secrets and never committed. On Actions, the
`actions_setup.py` step reconstructs them from repo secrets
(`SCRAPE_AUTHORIZATION`, `SCRAPE_WARMUP`) before any scrape step runs.

Mechanism: `jemscrape/secrets_io.py` `materialize_secret(name, path, env=...)`
reads the env var, and **fails closed** — raises `ConfigError` — if the secret
is missing or blank. `actions_setup.py` catches that and exits non-zero
(`exit 2`) with a `BLOCKED` message, before any fetch happens. Files are
written with restrictive permissions (`0o600`, set via `os.open` mode plus an
`fchmod` before the first byte, with `O_NOFOLLOW` so a symlink can't redirect
the write).

For authenticated projects there is a third, **conditional** secret,
`SCRAPE_STORAGE_STATE`, materialized to `.scrape-session.json` — but only when
`config.json` has `auth_required: true`. `actions_setup.py`'s `build_targets`
reads the config and adds it to the required set in that case; for a public
project the secret is simply absent and never looked at. When it is required
and missing, the same fail-closed `exit 2` applies before any fetch. The
captured session is a live credential (see `auth-session.md`), so it gets the
same 0600, gitignored, hook-guarded treatment as the other gate files.

## Workflow steps (`scrape.yml`)

1. `workflow_dispatch` + `schedule` (cron) triggers.
2. Checkout, `actions/setup-python@v5`.
3. **Materialize gate secrets** — `python actions_setup.py`, fed
   `SCRAPE_AUTHORIZATION` / `SCRAPE_WARMUP` from `secrets.*`.
4. **Compliance gate** — `python smoke_test.py` (fail-closed).
5. **Scrape** — `python scrape.py --limit 200`, a resumable chunk; picks up
   from `state/cursor.json`. `HTTPS_PROXY` is passed through from secrets when
   geo egress is needed (see `geo-proxy.md`).
6. **Build dataset** — `python build_dataset.py --records state/raw_records.json`
   assembles `exports/` (non-fatal today; wiring from `scrape.py`'s raw output
   to this step is per-project via `site_adapter`).
7. **Commit checkpoint** — commits `state/` and `exports/` with a bot identity;
   rebases and pushes; a failed push triggers `notify.py` and fails the job
   (the run must not silently lose its checkpoint).
8. **`actions/upload-artifact@v4`** — uploads `exports/` as a build artifact,
   independent of the git commit.
9. **Notify on failure** — `python notify.py` runs `if: failure()`.

Concurrency is limited to one run at a time (`concurrency: group: scrape,
cancel-in-progress: false`) so overlapping cron runs don't race on the
checkpoint.

## Chunking and cursor resume

`scrape.py --limit <N>` processes at most N items per invocation and updates
`state/cursor.json` as it goes. This lets a large catalog be scraped over many
scheduled runs, each cheap and within Actions' time limits, resuming exactly
where the last one stopped — including after a dropped/delayed cron run.

## What's versioned vs. gitignored

- **Versioned:** `exports/` (`products.csv`, `wiki/**.md`,
  `scrape_manifest.json`) and `state/cursor.json` — these are the deliverable
  and the resume checkpoint, both lightweight (markdown/CSV, not raw HTML).
- **Gitignored:** `data/` (raw HTML/JSON cache — can be large, may hold
  scraped third-party content) and the gate files
  (`.scrape-authorization.json`, `.scrape-warmup.json`, `*.token`, `*.secret`,
  `.env`). See `assets/project-skeleton/.gitignore`.

## Notify on failure

`notify.py` formats and emits a GitHub annotation (`::error::` / `::warning::`)
and is invoked on job failure, checkpoint push failure, or an auth-session
expiry mid-run (a 401/403 raises `AuthExpiredError`, which `scrape.py` catches,
flushes the records scraped so far, and reports via `notify.py` before exiting
non-zero). Default channel is a repo issue.

The `.yml` file is a **template**, scaffolded into a generated project's
`.github/workflows/` — it is not an active workflow in the plugin repo itself.
It's validated in the plugin's test suite by textual assertion of its steps
and guards, not executed.
