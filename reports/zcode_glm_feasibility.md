# Feasibility: extending the benchmark to ZCode CLI + GLM 5.2

**Date:** 2026-08-06
**Status:** investigation only — no implementation
**Context:** our harness (`experiments/run_experiment.py`) runs `claude -p --output-format stream-json --verbose`, captures `transcript.jsonl`, and computes token/tool-call metrics via `analyze_trajectory.py`. Question: can the same harness drive ZCode CLI + GLM 5.2?

## TL;DR

There is **no official "ZCode CLI."** ZCode is Z.ai/Zhipu's closed-source *desktop* IDE (Electron) built around GLM-5.2. A headless CLI runtime exists *inside* the app bundle (`zcode.cjs`), but it is undocumented, community-reverse-engineered, and its logging is far weaker than Claude Code's. A ZCode-based benchmark arm is **fragile but technically possible**; the **robust, recommended path** for a GLM-5.2 arm is Claude Code pointed at Z.ai's official Anthropic-compatible endpoint, which is officially documented and reuses our harness unchanged. Note that path benchmarks *GLM-5.2 the model under the Claude Code harness*, not *ZCode the agent product* — if the research question is about the ZCode agent itself, only the fragile path answers it.

## 1. Headless / batch execution

**Yes, with caveats (undocumented).** The bundled runtime supports single-shot runs:

```
zcode --prompt "<text>" [--cwd <dir>] [--mode plan|build|edit|yolo] [--attach <file>] [--resume <id>] [-c]
```

- Default headless mode is `yolo` (≈ our `--dangerously-skip-permissions`).
- **stdin piping is not supported** — long task cards must go via `--attach` or inline `--prompt`.
- The binary is not on PATH; it must be extracted/located from the desktop app install (`ZCODE_BIN` convention used by community tools).
- There is also a long-lived `zcode app-server --stdio` mode with a private JSON-RPC-like protocol (`session/create|send|read|messages|...`), used by community bridges.
- All flags come from reverse engineering (tizerluo/zcode-open-bridge, zcode-acp-server); Z.ai publishes zero CLI docs and any update can break them.

## 2. Running without interactive UI

Yes — `--prompt` runs fully non-interactively and exits; `app-server --stdio` runs as a driverable daemon. Neither requires the Electron UI. But both depend on the undocumented runtime above.

## 3. Data collection

| Signal | ZCode headless | How |
|---|---|---|
| Token usage | Partial | `--json` stdout: `{sessionId, response, usage: {inputTokens, outputTokens}, traceId, eventCount}`. **No cache tokens, no per-turn breakdown** in single-shot mode. App-server exposes `projection.totalTokenCount` and per-step `cost/tokens`. |
| Tool calls | Yes, indirectly | Message parts of `type: "tool"` (`callID`, `tool`, `state.{status,input,output}`) — retrievable only via app-server `session/messages`, or by reading the session store. |
| Trajectory | Yes, but SQLite | Sessions persist in `~/.zcode/cli/db/db.sqlite` (undocumented schema). No JSONL/plain-text transcript files. Message part types: `text`, `tool`, `reasoning`, `patch` (file hashes only, no diffs), `step-start`, `step-finish`. |
| Model responses | Yes | Final response in `--json` stdout; full turn-by-turn via app-server or SQLite. |
| Model/config | Yes | `~/.zcode/v2/config.json` (models keyed e.g. `GLM-5.2`, `baseURL`, `apiKey`); env: `ZCODE_MODEL`, `ZCODE_BASE_URL`, `ANTHROPIC_API_KEY` (the runtime speaks Anthropic protocol internally). |

## 4. Logging comparison vs Claude Code transcript JSONL

| Capability | Claude Code | ZCode headless |
|---|---|---|
| Headless flag | `-p` (official, stable) | `--prompt` (undocumented) |
| Streaming structured output | `--output-format stream-json` per-event JSONL | none — `--json` gives one final blob |
| Token accounting | per-turn input/output/**cache read/write** in every assistant event + result event totals | run-level input/output only; no cache split |
| Tool call log | every `tool_use`/`tool_result` inline in transcript JSONL | in SQLite DB / app-server protocol, not stdout |
| Transcript format | JSONL (also `~/.claude/projects/*.jsonl`) | SQLite (`~/.zcode/cli/db/db.sqlite`), undocumented schema |
| Turn/cost controls | `--max-turns`, allowed-tools, budget knobs | none found |
| Stability | official docs, semver CLI | reverse-engineered, "no guarantees" |

Net: ZCode's logging is materially weaker where our metrics live — cache-token accounting (central to a token-efficiency study) is **absent**, and trajectory extraction requires a SQLite adapter for an undocumented schema.

## 5. Minimal integration plan

**Option A (recommended): Claude Code + Z.ai GLM endpoint — officially supported, ~zero harness changes.**
Z.ai's GLM Coding Plan exposes an Anthropic-compatible endpoint documented for Claude Code (docs.z.ai/devpack/tool/claude):

1. Env for the agent subprocess only (add an `--agent glm` branch in `run_experiment.py` that injects env into the `subprocess.run` call):
   - `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`
   - `ANTHROPIC_AUTH_TOKEN=<Z.ai API key>`
   - `ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.2` (or `glm-5.2[1m]`), pass `--model` accordingly
   - optionally `API_TIMEOUT_MS=3000000`
2. Everything else — `stream-json` transcript, `analyze_trajectory.py`, verify.sh, metrics.json — works unchanged. Cache-token fields depend on Z.ai's endpoint populating them; validate on the smoke task first and note in results if cache accounting is absent.
3. Caveat: this measures **GLM-5.2 under Claude Code's scaffold** (Claude Code system prompt + tools), which is arguably the cleaner scientific comparison (same harness, model varies) — but it is *not* a benchmark of the ZCode agent product.

Estimated effort: ~1 hour + one smoke run to validate token fields from the Z.ai endpoint.

**Option B (only if the ZCode agent itself must be benchmarked): bundled runtime + SQLite adapter.**
1. Install ZCode desktop, locate `zcode.cjs`, pin the app version.
2. Runner branch: `zcode --prompt "$(cat task.md)" --cwd <workspace> --mode yolo --json` → capture stdout blob.
3. Write `zcode_trajectory.py`: read `~/.zcode/cli/db/db.sqlite` for the run's `sessionId`, extract tool parts and step tokens, normalize into our metrics schema.
4. Accept gaps: no cache tokens, no stream events, schema may break on any app update.

Estimated effort: 1–2 days, ongoing breakage risk. Not recommended unless "ZCode-the-product" is the object of study.

## Sources

- Official: https://zcode.z.ai (docs), https://docs.z.ai/devpack/overview, https://docs.z.ai/devpack/tool/claude, https://github.com/zai-org/feedback
- Community (reverse-engineered CLI details): https://github.com/tizerluo/zcode-open-bridge, https://www.npmjs.com/package/zcode-acp-server
- Note: npm `zcode-cli` is a **community** package, not from zai-org.
