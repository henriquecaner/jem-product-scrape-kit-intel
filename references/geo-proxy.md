# Geo / Proxy

How country-specific egress is handled (design spec §5, §5.2, §12, achado #35).

## The proxy is org-provisioned, not per-user

A shared JEM proxy account (residential, country egress on demand — e.g. UK)
is provisioned **once by IT**, not contracted individually by each user. This
is an explicit org prerequisite (design spec §19), delivered as a managed
secret, not a credential the scraping user signs up for.

## HTTP path: `HTTPS_PROXY`

For the stdlib HTTP fetch path, setting the `HTTPS_PROXY` environment variable
is sufficient — Python's `urllib`/`http.client`-based fetcher honors it like
any standard HTTP client. On the Actions runtime this is passed in as a repo
secret and exported as an env var for the scrape step (see
`runtime-github-actions.md`).

## Browser path: proxy must go on the Playwright launch

`HTTPS_PROXY` alone does **not** cover the browser render path. A headless
Chromium instance launched by Playwright does not automatically inherit or
honor the `HTTPS_PROXY` env var for its own network stack. The proxy has to be
passed explicitly to the browser launch call.

In `drivers/playwright_render.py`, `render(url, *, timeout, proxy=None,
user_agent=None)` accepts a `proxy` argument (a Playwright proxy dict) and, if
given, includes it in `launch_kwargs` passed to `chromium.launch(...)`. This
is the only correct way to route browser traffic through the country-egress
proxy — setting `HTTPS_PROXY` in the environment and expecting the browser to
pick it up is the mistake this driver is built to avoid.

## Detection: warm-up flags geo/anti-bot

The warm-up lap's recon (`jemscrape/recon.py`) flags anti-bot/geo signals
(Cloudflare challenge, recurring 429s, geo-block) and recommends configuring a
country-egress proxy or promoting the run to a VM — this is one of the four
signals measured before a full run is allowed (see the warm-up section of the
design spec, §9.1).

## Cost

The proxy is a paid service (residential UK pricing is roughly US$1.75+/GB in
the design spec's estimate), but paced scraping (see `anti-ban-playbook.md`)
uses little bandwidth per run.
