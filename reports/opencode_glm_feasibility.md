# Feasibility: migrating the token-efficiency benchmark to OpenCode (+ GLM-5.2)

**Date:** 2026-08-06
**Status:** investigation only — no benchmark code modified
**Researched version:** OpenCode v1.18.14 (SST, open source, released 2026-08-05). Not yet installed on this machine.
**Context:** current harness = `claude -p --output-format stream-json` → `transcript.jsonl` → `analyze_trajectory.py`. Question: can OpenCode replace Claude Code as the agent scaffold, driving GLM-5.2?

## TL;DR

**Feasible, and cleanly so.** OpenCode has an official headless mode (`opencode run --format json`) that streams NDJSON events, officially supports Z.ai's GLM Coding Plan (GLM-5.2 is a first-class model ID), and exposes per-message token accounting **including cache read/write** — the field our study depends on and which ZCode lacked. All five signals we need (input tokens, output tokens, tool calls, trajectory) are extractable from three redundant sources: the stdout event stream, stored per-message JSON files, and `opencode export`. Main costs: a new transcript parser (event schema differs from Claude Code's), version pinning (daily release cadence, storage migration in flight), and the caveat that results won't be comparable to our Claude Code baseline numbers — different scaffold, different system prompt, different tools.

## 1. Headless CLI — yes (official)

`opencode run "<prompt>"` is documented for scripting/automation (opencode.ai/docs/cli):

- `-m provider/model` — model selection
- `--format json` — raw JSON events on stdout
- `--auto` — auto-approve permissions (hidden aliases `--yolo`, `--dangerously-skip-permissions`; without it, run mode auto-*rejects* permission requests, so this flag is mandatory for us)
- `--dir <path>` — working directory (replaces our `cwd=workspace` subprocess handling)
- `--session`/`--continue`/`--fork` for continuation; `--file` to attach files
- Also `opencode serve` — headless HTTP server (default port 4096, OpenAPI spec at `/doc`) if we ever want API-driven runs.

Harness mapping is one-to-one with our current `claude -p` invocation:

| Claude Code (current) | OpenCode equivalent |
|---|---|
| `claude -p "<prompt>"` | `opencode run "<prompt>"` |
| `--output-format stream-json --verbose` | `--format json` (NDJSON events) |
| `--model claude-sonnet-5` | `-m zai-coding-plan/glm-5.2` |
| `--dangerously-skip-permissions` | `--auto` |
| `cwd=workspace` | `--dir workspace` (or keep cwd) |

## 2. GLM-5.2 via API — yes (officially documented on both sides)

- Z.ai officially lists OpenCode under the GLM Coding Plan: docs.z.ai/devpack/tool/opencode. Setup: `opencode auth login` → provider "Z.AI Coding Plan" → paste API key.
- OpenCode's provider registry (models.dev) has provider `zai-coding-plan` with **`glm-5.2`**, `glm-5.2-highspeed`, `glm-5-turbo`, `glm-4.7`; baseURL `https://api.z.ai/api/coding/paas/v4` (OpenAI-compatible), env `ZHIPU_API_KEY`.
- Model flag for the harness: **`-m zai-coding-plan/glm-5.2`**. (Pay-per-token alternative: provider `zai`, baseURL `https://api.z.ai/api/paas/v4`.)
- Note: OpenCode uses Z.ai's OpenAI-compatible endpoint, not the Anthropic-compatible one Claude Code uses. Same models, different wire protocol.

## 3. Endpoint configuration

Two options:

1. **Built-in provider (recommended):** `opencode auth login` → Z.AI Coding Plan, or set `ZHIPU_API_KEY`. Model limits/pricing come from models.dev automatically. Credentials land in `~/.local/share/opencode/auth.json`.
2. **Manual override** in `opencode.json` (project-local or `~/.config/opencode/`), for pinning or non-registry endpoints:

```json
{
  "provider": {
    "zai-coding-plan": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "https://api.z.ai/api/coding/paas/v4",
        "apiKey": "{env:ZHIPU_API_KEY}"
      }
    }
  }
}
```

A project-local `opencode.json` inside each task workspace also gives per-run isolation, matching how we isolate `.claude/skills/` today.

## 4. Logs / transcripts available

Three redundant sources, all structured:

1. **stdout NDJSON** (`--format json`): one JSON object per event line — `{type, timestamp, sessionID, ...}` with types including `text`, `tool_use`, step and error events. This is the direct analogue of our `transcript.jsonl` capture. *Caveat: the full per-type event schema isn't documented; verify empirically on the pinned version.*
2. **Stored session files:** `~/.local/share/opencode/project/<slug>/storage/` — pretty-printed JSON, one file per record, in `session/`, `message/<sessionID>/`, `part/<messageID>/` directories. *Caveat: v1.18.x also ships an `opencode db` SQLite command — a storage migration is in flight; check `opencode db path` on the installed build and prefer sources 1/3 over scraping raw paths.*
3. **`opencode export <sessionID>`** — official full-transcript JSON dump (plus `opencode stats` for aggregate token/cost figures with `--models`, `--tools` breakdowns).

## 5. Extractable signals — all four, with exact fields

From the SDK types (authoritative, `packages/sdk/js`):

| Signal | Where | Fields |
|---|---|---|
| Input tokens | per assistant message | `tokens.input` |
| Output tokens | per assistant message | `tokens.output` (plus `tokens.reasoning`) |
| **Cache tokens** | per assistant message | `tokens.cache.read`, `tokens.cache.write` — present, unlike ZCode; critical since 84–94% of tokens in our study were cache re-reads |
| Cost | per message and per step | `cost` (USD) — computed by OpenCode from models.dev pricing, a field we currently derive ourselves |
| Tool calls | `ToolPart` parts | `callID`, `tool` (name), `state.{status, input, output, time.start/end}` |
| Trajectory | full message/part sequence | via event stream, stored JSON, or `opencode export` |
| Per-step tokens | `StepFinishPart` | same `cost` + `tokens` shape, finer-grained than Claude Code gives us |

Whether Z.ai's OpenAI-compatible endpoint actually populates the cache fields (vs returning zeros) needs one smoke run to confirm — same open question we flagged for the Claude Code + Z.ai path.

## Comparison with Claude Code transcript JSONL

| Capability | Claude Code | OpenCode |
|---|---|---|
| Headless flag | `-p` | `opencode run` — equivalent |
| Stream JSON | `--output-format stream-json` | `--format json` — equivalent concept, **different event schema** |
| Token accounting | input/output/cache per turn | input/output/reasoning/cache.read/cache.write per message + per step — equal or better |
| Cost | derived by us | native `cost` field |
| Tool logging | `tool_use`/`tool_result` events | `ToolPart` with status/timing — equivalent |
| Transcript export | JSONL files | `opencode export` JSON + stored JSON files |
| Turn limits / tool allowlist | `--max-turns`, allowed-tools | not found — check on pinned version |
| Stability | official, stable | official but ~daily releases; storage backend migrating JSON→SQLite |

## Migration plan sketch (not implemented)

1. Install OpenCode, **pin the version**, run `opencode auth login` (Z.AI Coding Plan) or set `ZHIPU_API_KEY`.
2. Smoke run: `opencode run "hello" -m zai-coding-plan/glm-5.2 --format json --auto` → capture NDJSON, confirm event schema and that `tokens.cache.*` are populated by the Z.ai endpoint.
3. Add an agent branch to the runner (new function alongside `run_agent`, per the do-not-modify-analyzer constraint — likely a sibling script or a `--agent` switch): swap the command line per the mapping table above; keep workspace build/verify.sh unchanged.
4. Write `analyze_opencode_trajectory.py` mirroring `analyze_trajectory.py`'s output schema (`tokens.total.*`, `tool_calls.total`, …) so `metrics.json`, `summarize_runs.py`, and the report tables work unchanged. Prefer parsing the stdout NDJSON (self-contained per run); fall back to `opencode export` if the stream proves lossy.
5. Re-baseline: OpenCode results are **not comparable** to existing Claude Code numbers (different scaffold, system prompt, tool set, and the calibration finding that Claude Code's default discipline already avoids the target waste may not hold for OpenCode + GLM-5.2 — arguably that makes it a *more* interesting testbed for Skill v1, since a weaker default discipline leaves more recoverable waste).

Estimated effort: ~0.5 day for runner branch + parser + smoke validation, assuming the event schema is sane.

## Risks

- **Event schema undocumented** — must be characterized empirically; pin the version and snapshot a reference transcript.
- **Release velocity** (~1/day) and JSON→SQLite storage migration — don't scrape storage paths; rely on stdout stream and `export`.
- **Cache-token fidelity from Z.ai's endpoint** unverified — gate the migration on the smoke run.
- **No `--max-turns` equivalent found** — runaway runs bounded only by our subprocess timeout.
- **Skill mechanism differs**: OpenCode has no `.claude/skills/` — the skill arm would need `AGENTS.md`, a custom agent definition, or prompt injection; the "explicit skill invocation" manipulation must be redesigned and documented as a protocol change.

## Sources

- CLI/docs: https://opencode.ai/docs/cli/, /docs/server/, /docs/providers/, /docs/troubleshooting/
- Z.ai official OpenCode setup: https://docs.z.ai/devpack/tool/opencode; endpoints: https://docs.z.ai/devpack/quick-start
- Model registry: https://models.dev/api.json (providers `zai-coding-plan`, `zai`)
- Source/SDK: github.com/sst/opencode — `packages/opencode/src/cli/cmd/run.ts`, `packages/sdk/js/src/gen/types.gen.ts`; releases page for cadence
