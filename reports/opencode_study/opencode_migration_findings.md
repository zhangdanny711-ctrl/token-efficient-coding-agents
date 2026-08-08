# OpenCode migration — smoke-test findings

**Date:** 2026-08-06
**Status:** execution + logging verified end-to-end; no benchmark code modified
**Installed version:** OpenCode **1.18.14** (npm `opencode-ai`, global) — pin this; releases are ~daily.
**Reference artifacts:** `experiments/opencode_smoke/oc_smoke_transcript.ndjson` (stdout NDJSON), `experiments/opencode_smoke/oc_export.json` (`opencode export` dump), from a real run of the existing `tasks/smoke` task.

## TL;DR

OpenCode headless execution works end-to-end: the smoke task ran to completion, the fix passed `verify.sh` (5/5 tests), and **all five signals we need are extractable** — input tokens, output tokens, cache read/write tokens, tool calls, and full trajectory. One deviation from plan: **no Z.ai API key exists on this machine**, so GLM-5.2 via `zai-coding-plan` could not be configured. The smoke test instead used **`amazon-bedrock/zai.glm-5`** (GLM-5 on Bedrock, first-class in OpenCode's registry, already AUTHORIZED on this AWS account). Decision needed: obtain a `ZHIPU_API_KEY` for exact GLM-5.2, or adopt Bedrock GLM-5 as the study model.

## 1. Installation & CLI — verified

- `npm install -g opencode-ai` → `opencode 1.18.14`.
- `opencode run "<prompt>" -m <provider/model> --format json --auto` behaves as the feasibility report predicted. `--dir` exists; we ran with `cwd=workspace` instead (works fine).
- Confirmed: **no `--max-turns` equivalent** in `run --help`. Runaway bound = our subprocess timeout only.

## 2. Model access — Bedrock GLM-5 works; Z.ai GLM-5.2 blocked on key

| Path | Model flag | Status |
|---|---|---|
| Z.ai Coding Plan (plan A) | `-m zai-coding-plan/glm-5.2` | **Blocked** — no `ZHIPU_API_KEY` anywhere on this machine (env, configs, AWS Secrets Manager all checked) |
| Bedrock (plan B, used) | `-m amazon-bedrock/zai.glm-5` | **Works** with existing AWS creds + `AWS_REGION=us-east-1`. `zai.glm-5`, `zai.glm-4.7`, `zai.glm-4.7-flash` all AUTHORIZED/AVAILABLE on account 521102048267 |

Note GLM-5 ≠ GLM-5.2; if the study must be exactly GLM-5.2, we need a Z.ai key (`opencode auth login` → "Z.AI Coding Plan", or `export ZHIPU_API_KEY=...`). Everything below is model-independent.

## 3. Smoke run — PASS

```
cd <workspace>
AWS_REGION=us-east-1 opencode run "$(cat task.md)" -m amazon-bedrock/zai.glm-5 --format json --auto > transcript.ndjson
```

- Task: existing `tasks/smoke` (fix `average_word_length`), fresh copy of `repo/`.
- Result: agent fixed the bug in 5 steps / 7 tool calls (glob 1, bash 3, read 2, edit 1); `verify.sh` → **5 passed**, exit 0.
- Totals (from `opencode export` session info): input 40,824 / output 318 / cache 0/0 / cost $0.0418.

## 4. Log format — characterized empirically

**Source 1 — stdout NDJSON** (`--format json`): one event per line:

```json
{"type": "step_start"|"text"|"tool_use"|"step_finish", "timestamp": ..., "sessionID": "ses_...", "part": {...}}
```

- Every `part` carries `id`, `messageID`, `sessionID` — events group into assistant messages via `messageID`.
- `part.type == "tool"`: `tool` (name), `callID`, `state.{status, input, output, metadata}` — **tool inputs AND full outputs are in the stream**, so long-output detection works.
- `part.type == "step-finish"`: `reason`, `cost` (USD), `tokens.{total, input, output, reasoning, cache.{read, write}}` — **per-step token accounting including cache fields**.
- `part.type == "text"`: assistant prose with start/end times.
- No terminal `result` event with session totals — totals come from summing `step_finish` or from source 2.
- Tool names are lowercase (`read`, `edit`, `bash`, `glob`, ...) vs Claude Code's capitalized names.

**Source 2 — `opencode export <sessionID>`**: single JSON `{info, messages: [{info, parts}]}`.
- Session `info`: aggregate `tokens`, `cost`, `version`, `model`, timing.
- Per assistant message `info`: `tokens` (same shape), `cost`, `modelID`, `providerID`, `finish`.
- Storage is now **SQLite** (`~/.local/share/opencode/opencode.db`) — the per-file JSON storage described in the feasibility report is gone in 1.18.14; the migration it flagged has landed. Use export/stdout, never the DB directly. `export` needs the session's project dir as cwd (or `--dir`).

## 5. Signal checklist

| Signal | Available | Where |
|---|---|---|
| Input tokens | ✅ | `step_finish.part.tokens.input` (per step); message/session `info.tokens.input` in export |
| Output tokens | ✅ | `...tokens.output` + `...tokens.reasoning` (keep separate or fold in) |
| Cache read/write | ✅ field present | `...tokens.cache.{read,write}` — **but Bedrock GLM-5 returned all zeros** in the smoke run; either no prompt caching on this path or unreported. Input grows step-over-step (7.3k→8.7k), consistent with genuinely uncached full-context resends. Must re-check on the Z.ai endpoint before any cache-dependent analysis |
| Tool calls | ✅ | `tool_use` events: name, input, output, status, timing |
| Full trajectory | ✅ | NDJSON stream (self-contained per run) + export as backup |
| Cost | ✅ bonus | native `cost` per step/message/session |
| Subagent attribution | ⚠️ untested | no `parent_tool_use_id` analogue seen; smoke run spawned no subagents. Characterize if/when a task uses OpenCode's task tool |

## 6. Proposed minimal adapter (not yet built)

Reuse `analyze_trajectory.py`'s output schema exactly so `metrics.json`, `summarize_runs.py`, and report tables work unchanged. Two small pieces, zero changes to existing files:

1. **`analyze_opencode_trajectory.py`** (~150 lines): parse the NDJSON transcript; group parts by `messageID` → "main turns"; map
   - `tokens.input → input_tokens`, `tokens.output + tokens.reasoning → output_tokens`, `tokens.cache.read → cache_read_input_tokens`, `tokens.cache.write → cache_creation_input_tokens` (sum `step_finish` events; verified this yields the same totals as the export's session info);
   - tool names: `read→Read`, `edit→Edit`, `write→Write`, `bash→Bash`, `glob/grep→Glob/Grep`, `task→Task`; input key `filePath→file_path`;
   - behavior metrics (search-before-read, repeated reads, long outputs, test-sequence) port directly — tool inputs/outputs are all in the stream;
   - emit `result` block from summed cost + wall time (no native result event); `tokens.subagent` stays zero until subagent attribution is characterized.
2. **Runner branch**: sibling script `run_experiment_opencode.py` (or `--agent opencode` switch) that swaps only the command line — `opencode run <prompt> -m <model> --format json --auto`, cwd=workspace — keeping workspace build and `verify.sh` untouched.

Proof-of-concept mapping already validated against the smoke transcript (totals match export: 40,824 in / 318 out / 7 tool calls).

**Known protocol gaps to document, not solve now:** (a) skill arm needs a new injection mechanism (`AGENTS.md` in workspace is the natural analogue of `.claude/skills/`); (b) no max-turns cap; (c) results not comparable to Claude Code numbers — re-baseline required.

## Open decisions before proceeding

1. **Model**: get `ZHIPU_API_KEY` for exact GLM-5.2, or accept Bedrock `zai.glm-5`?
2. **Cache accounting**: if cache tokens stay zero on the chosen endpoint, the "84–94% cache re-read" analysis from the Claude Code study has no analogue — token totals then measure raw resent context, which changes how Skill v1's rules should be scored.

## Update (same day): GLM-5.2 via Z.ai verified — both decisions resolved

`ZHIPU_API_KEY` added to `~/.bashrc` (line 143 — after the interactivity guard's `return`, so scripts must export it explicitly rather than rely on sourcing). Connectivity test:

```
opencode run "hi" -m zai-coding-plan/glm-5.2 --format json
```

- **Works** — same NDJSON event schema as the Bedrock run, adapter design unaffected.
- **Cache tokens ARE populated**: first turn already shows `cache: {read: 4992, write: 0}` with `input: 2143` — unlike Bedrock GLM-5's all-zeros. The cache re-read analysis from the Claude Code study has a direct analogue here.
- **`cost: 0`** — the coding-plan subscription reports no per-token cost, so dollar-delta comparisons need external pricing (or the pay-per-token `zai` provider).
- Decision: study model = **`zai-coding-plan/glm-5.2`**.
