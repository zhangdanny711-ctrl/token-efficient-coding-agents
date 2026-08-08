# OpenCode + GLM-5.2 smoke test result

**Date:** 2026-08-06
**Status:** pipeline works end-to-end for both conditions; paused before formal benchmark per plan.
**Versions:** OpenCode 1.18.14 (pinned), model `zai-coding-plan/glm-5.2` (Z.ai Coding Plan, OpenAI-compatible endpoint).

## TL;DR

Both smoke runs **PASS** `verify.sh` (5/5 tests), transcripts captured, **cache tokens populated** (33k–52k cache reads), and the new analyzer emits the exact `metrics.json` schema the Claude Code pipeline uses. Two real issues were found and fixed along the way: (1) OpenCode must be launched with `--dir <workspace>` or the agent escapes the workspace, and (2) the frozen `tasks/smoke/repo` had been contaminated — a previous agent run had fixed the bug *in the task source itself* (restored, plus `__pycache__` purge). One protocol difference is unavoidable: skill injection is via `AGENTS.md`, always-loaded, with no explicit invocation line in the prompt.

## New files (existing Claude Code pipeline untouched)

| File | Role |
|---|---|
| `experiments/run_opencode_experiment.py` | sibling runner: same task layout / verify.sh / metrics.json record shape; run dirs prefixed `oc_` |
| `experiments/analyze_opencode_trajectory.py` | NDJSON parser; same output schema as `analyze_trajectory.py` (imports its constants so thresholds/classifiers stay in sync) |

## Command used

```
python3 run_opencode_experiment.py --task tasks/smoke --condition {baseline|skill} --run-id oc1
# underlying agent call:
opencode run "<task.md>" --format json --auto -m zai-coding-plan/glm-5.2 --dir <workspace>
```

`ZHIPU_API_KEY` is read from env, falling back to parsing `~/.bashrc` (the export line sits below the interactivity guard, so non-interactive shells can't source it).

## Results (tasks/smoke, ×1 each)

| condition | verify | input | output | cache read | cache write | grand total | tool calls | turns | duration |
|---|---|---|---|---|---|---|---|---|---|
| baseline | **PASS** | 7,385 | 360 | 33,088 | 0 | 40,833 | 6 (Bash 2, Read 3, Edit 1) | 5 | 8.5s |
| skill | **PASS** | 3,099 | 332 | 51,712 | 0 | 55,143 | 7 (Glob 2, Read 2, Edit 1, Bash 2) | 6 | 12.8s |

Observations (n=1, no conclusions):

- **Cache tokens are real on the Z.ai endpoint** — the dominant token bucket, same qualitative shape as the Claude Code study (cache re-reads ≫ fresh input). `cache_write` = 0 throughout; Z.ai appears to report only reads.
- AGENTS.md is verifiably loaded: first-turn context is 8,482 vs 7,436 tokens (+ ~1,050 ≈ the SKILL.md body), and the skill run's behavior shifted (led with Glob searches before reading — Rule 1).
- Skill run: fewer input tokens but more turns → more cache re-reads → higher grand total. Echoes the fixed-overhead pattern from the Claude Code study; formal runs will quantify.
- `cost` is 0 on the coding plan (subscription) — dollar analysis needs external pricing or the pay-per-token `zai` provider.

## Skill injection protocol (differs from Claude Code arm)

| | Claude Code arm | OpenCode arm |
|---|---|---|
| Mechanism | `.claude/skills/token-efficient-coding/SKILL.md` copied into workspace | SKILL.md body (frontmatter stripped) written to `<workspace>/AGENTS.md` |
| Prompt | task.md + explicit "Use the token-efficient-coding skill..." line | task.md only — **identical prompt in both conditions** |
| Loading | on-demand (agent reads the skill in a turn) | unconditional (injected into system context at session start) |

Consequences: the OpenCode skill arm has no "extra skill-read turn" overhead (the ~40k/task fixed cost in the Claude Code study), but pays ~1k tokens of always-on context per turn instead. Baseline vs skill remains a single-variable comparison *within* the OpenCode arm; comparisons *across* arms are protocol-confounded.

## Transcript schema (NDJSON, `--format json`)

One event per line: `{"type", "timestamp", "sessionID", "part"}` with part types `step-start`, `text`, `tool`, `step-finish`:

- `tool` part: `tool` (lowercase name), `callID`, `state.{status, input, output, metadata}` — full inputs and outputs in-stream.
- `step-finish` part: `reason`, `cost`, `tokens.{total, input, output, reasoning, cache.{read, write}}`.
- Parts carry `messageID` → grouping into assistant turns.
- No terminal result/totals event — analyzer sums `step_finish` (verified equal to `opencode export` session totals).

## Analyzer mapping (`analyze_opencode_trajectory.py`)

- `tokens.input → input_tokens`; `tokens.output + tokens.reasoning → output_tokens` (raw reasoning preserved as `tokens.reasoning_raw`); `cache.read/write → cache_read/creation_input_tokens`.
- Tool names normalized (`read→Read`, `glob→Glob`, …); `filePath → file_path` handling for Read/Edit/Write.
- All behavior metrics (search-before-read, repeated reads, long outputs, test ordering, text volume) computed from tool parts; tool parts deduped by `callID` (stream may restream a part as state advances).
- `result` block synthesized from summed cost + timestamp span (no native equivalent).
- Validated against the earlier Bedrock reference transcript: totals match `opencode export` exactly (40,824 in / 318 out / 7 calls).

## Compatibility issues vs Claude Code pipeline

1. **`--dir` is mandatory.** Without it, OpenCode resolved a project root above the workspace (workspaces aren't git repos) and the first baseline attempt escaped into `experiments/tasks/smoke/repo/` — the frozen task source — and "fixed" it there. Runner now always passes `--dir <workspace>`. A containment check over the transcript confirmed the rerun touched only workspace paths.
2. **Task-repo contamination found & fixed:** `tasks/smoke/repo/textstats/stats.py` had already been bug-fixed in place (residue of the escaped run and/or an earlier accident) and `__pycache__` was present. Restored the `- 1` bug, purged caches, confirmed buggy state fails 1/5 tests. **Frozen task repos should be re-audited before any formal batch** (same class of issue as the v1 `__pycache__` invalidation).
3. **No subagent attribution.** No `parent_tool_use_id` analogue observed; `tokens.subagent` stays zero. Rule 2 (delegation) can't be measured the same way — flag when designing the formal OpenCode benchmark.
4. **`output_tokens` includes reasoning** (folded to match Claude Code's billing convention); raw value kept separately.
5. **`cost=0`** on coding plan; `total_cost_usd` in metrics is only meaningful on pay-per-token providers.
6. **No `--max-turns`** — runaway bound is the runner's 900s subprocess timeout only.
7. **`cache_write` always 0** from Z.ai — cache-economics analyses that need write pricing can't be replicated exactly.

## Next (not started, per instruction)

Formal benchmark on OpenCode is unblocked. Before running: re-audit all frozen task repos for contamination; decide how to handle Rule 2 measurement; decide token-vs-dollar reporting given `cost=0`.
