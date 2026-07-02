# Execution Strategy

Models, effort levels, and thinking settings for tasks in this plugin (design
spec §11).

## Hard rule

**Never use Haiku.** This is a fixed JEM policy, not a per-task judgment call.
The economical tier is **Sonnet 5 `medium`**, not Haiku.

## Infra boundary by runtime

- **Local runtime** (Claude Code session) — LLM normalization runs as
  subagents/workflows inside Claude Code, billed to the subscription. Prompt
  caching applies. Batch API does **not** apply here — Batch is a feature of
  direct Anthropic API billing, and the subscription doesn't route through it.
- **Actions runtime** (unattended, `build_dataset.py`) — no Claude Code
  process is running. Normalization is a Python step that calls the Anthropic
  API directly with `ANTHROPIC_API_KEY` (an Actions secret). This is the
  **only** path where Batch API (−50%) and caching both apply. The API key is
  an org prerequisite (§19 of the design spec), not something the user
  provisions.

## Model/effort table

| Task | Model | Effort | Thinking | Orchestration |
|---|---|---|---|---|
| Purely mechanical parsing | Deterministic code (no LLM) — Opus infers the parser once | — | — | — |
| Simple semantic extraction at scale | Sonnet 5 | medium | off | Local: subagents · Actions: script + Batch + caching |
| Normalization requiring judgment (category, matching, quality) | Sonnet 5 | medium | on | Local: subagents (pipeline) · Actions: script + Batch + caching |
| Parser inference / audit | Opus | xhigh | on | Workflow when risks are detected (parallel dimensions + adversarial verification) |
| Warm-up lap green-light review | Opus 4.8 (reviewer) + Sonnet 5 (advisor) | xhigh / medium | on | Two-agent workflow: advisor raises risks, reviewer decides. Mandatory gate before any full run. |
| Compare ours vs. competitors (Layer 2, future) | Sonnet 5 / Opus | medium/high | on | Workflow (fan-out per product) |

## Cost levers

- **Batch API (−50%)** — Actions runtime only (script + API key).
- **Prompt caching** — any runtime.
- **Thinking off** for mechanical parsing / simple extraction; **thinking on**
  for anything requiring judgment (categorization, matching, the warm-up
  review, audits).
- Batch requires an API key and API billing; the Claude Code subscription
  (Local runtime) does not route through Batch.

## What's built vs. future

The deterministic pipeline (fetch → parse → normalize → dedup → export) is the
v1 reality and needs no LLM calls at runtime. LLM-assisted normalization
(semantic extraction, judgment-based normalization) is **not yet built** — it
is the Layer 2 hook described above, wired into `build_dataset.py` on Actions
once it exists. Until then, the Actions runtime has no `ANTHROPIC_API_KEY`
dependency in practice.
