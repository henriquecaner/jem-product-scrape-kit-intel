---
description: Start a new scraping project — a guided wizard through the compliance gate, warm-up lap, run-plan, and scrape.
argument-hint: "[target URL]"
---

Start a new product-scraping project.

Use the **scrape-product-catalog** skill as a **guided wizard** — the JEM operator is non-technical, so ask one question at a time, explain each step in plain language, and confirm before each gate. Never batch the questions.

Wizard sequence:

1. **Understand the target** — ask for the URL, then: is this authorized (public competitor / contracted supplier / own account)? Does it need a specific country IP? Does it need to run on a schedule?
2. **Compliance gate** (`scrape-compliance-gate`) — read the site's `robots.txt`, write/validate `.scrape-authorization.json`, confirm the robots precedence matrix. Fail-closed.
3. **Scaffold** the project from `assets/scraper-template/` and adapt the site selectors.
4. **Warm-up lap** (`scrape-warmup`, MANDATORY) — sample 10–50 products, detect render/auth/anti-bot/shape, then run the 2-agent green-light review.
5. **Run-plan** (`scrape-run-plan`) — present scope, ETA, cost, and risks; get approval.
6. **Run** — only with a GREEN warm-up verdict and (if required) run-plan approval.
7. **Normalize + export** (`scrape-normalize-export`) — canonical CSV + wiki.

Do not skip the warm-up lap, and do not start the full scrape without a GREEN verdict.
