# Estimation (ETA / Cost)

How the run-plan estimates time and cost before a full run (design spec §11,
§9.1). There is no standalone estimator module yet — these are the rules the
`scrape-run-plan` skill applies using numbers the warm-up lap measures.

## ETA

```
ETA ~= URL count x rate-limit floor
```

The engine is single-threaded and pacing-dominated (see
`anti-ban-playbook.md` — `jemscrape/pacing.py`): each request waits at least
`rate_limit_floor_seconds`, plus randomized jitter up to `max_delay_seconds`,
plus periodic 90-240s coffee breaks every 20-30 requests. Because there's no
concurrent fan-out against the target site, total wall-clock time scales
linearly with URL count and is bounded below by the floor. The floor and
delay range come from `config.json` (`rate_limit_floor_seconds`,
`min_delay_seconds`, `max_delay_seconds`), validated by
`jemscrape/config.py`.

The warm-up lap (10-50 sampled products) gives a real per-request timing
sample instead of a guess, so the ETA in the run-plan is evidence-based, not
assumed.

## Cost

**v1 (current, deterministic normalize): effectively zero LLM cost.** The
pipeline (fetch -> parse -> normalize -> dedup -> export) is deterministic
code, no LLM calls at runtime. The only LLM usage in the current build is the
one-time parser inference during scaffold (Opus, high effort) and the
mandatory warm-up green-light review (Opus 4.8 `xhigh` + Sonnet 5 advisor,
design spec §9.1) — both fixed, small, one-off costs per project, not
per-product.

**Future, when LLM normalization is added (Layer 2):** cost scales with
product count and only applies on the Actions runtime, where
`build_dataset.py` would call the Anthropic API directly. **Batch API (−50%)
applies only there** — Local runtime normalization runs as Claude Code
subagents against the subscription and never routes through Batch (see
`execution-strategy.md`). Prompt caching reduces repeated-context cost on
either runtime once LLM normalization exists.

## What feeds the run-plan

Both ETA and cost in the run-plan skill are meant to come from the warm-up
lap's recon output (actual per-request latency, sample coverage, detected
render/auth/anti-bot signals) rather than from assumptions made before ever
touching the target site — this is the point of making the warm-up mandatory
before any full run.
