# Token-Efficient Coding Agents

> A controlled study of whether a prompt-level policy can reduce coding-agent token use without reducing task completion quality.

**Personal research project by Enze Zhang · July–August 2026**

[Read the skill](.claude/skills/token-efficient-coding/SKILL.md) · [Research report](docs/RESEARCH_REPORT.md) · [Study design](docs/STUDY_DESIGN.md) · [Literature review](docs/LITERATURE_REVIEW.md)

## Summary

I designed a five-rule token-efficiency skill and built a Python evaluation harness for isolated, headless coding-agent runs. The harness records complete trajectories, derives token and tool-use metrics, and re-tests agent-modified source against fixed acceptance suites in clean verification directories.

The result was environment-dependent:

- **OpenCode + GLM-5.2:** the skill reduced mean total token use by **19.1%** in a 20-vs.-20 controlled comparison (`p=0.0094`).
- **Historical open-source bugs:** the reduction grew to **36.1%** across 48 runs on six bugs from TinyDB, Tabulate, Boltons, more-itertools, and Funcy (`p=0.0003`).
- **Task quality:** all **88 headline runs** passed automated verification.
- **Claude Code + Sonnet:** a calibration gate found that the baseline already exhibited the targeted behaviors, so the planned expansion was stopped early. Earlier small-task validation showed that explicit skill invocation added overhead when there was little waste to remove.

The practical finding is not that every coding agent should use the same efficiency prompt. A policy pays off only when the underlying agent–model stack leaves recoverable behavioral waste.

## Headline results

| Evaluation | Design | Baseline | Full skill | Effect | Verification |
|---|---:|---:|---:|---:|---:|
| Controlled lab tasks | 20 baseline vs. 20 skill | 184,245 mean tokens | 149,092 mean tokens | **−19.1%**, `p=0.0094` | 40/40 pass |
| Six historical OSS bugs | 6 tasks × 2 arms × 4 runs | task-level baseline medians | task-level skill medians | **−36.1%**, `p=0.0003` | 48/48 pass |
| Hardest underspecified tier | 3 tasks × 2 arms × 4 runs | task-level baseline medians | task-level skill medians | **−38.8%**, `p=0.01` | 24/24 pass |

The released archive contains 230 `metrics.json` records. Four baseline runs are explicitly marked as contaminated and excluded; all **226 valid archived runs** pass their configured verification.

## The five-rule skill

The deployable artifact is [`.claude/skills/token-efficient-coding/SKILL.md`](.claude/skills/token-efficient-coding/SKILL.md). It is a prompt-level intervention: no model weights or harness internals are modified.

1. **Acquire minimal context.** Search before reading, inspect only relevant ranges, avoid unchanged re-reads, and constrain long command output.
2. **Delegate wide exploration.** Use a focused exploration subagent only when the answer genuinely spans several files.
3. **Stop unproductive paths.** Change approach after repeated attempts produce no new evidence.
4. **Match effort to the task.** Use direct locate–fix–verify loops for local changes and escalate planning only when complexity warrants it.
5. **Keep output scoped.** Make targeted edits and report conclusions and verification evidence without replaying the full process.

## Evaluation harness

Each run follows the same lifecycle:

```text
frozen task template
        ↓ copy
isolated per-run workspace
        ↓
headless coding agent edits source
        ↓
trajectory parser records tokens, turns, reads, and tool use
        ↓
clean verification directory combines agent source with fixed tests
        ↓
PASS / FAIL + metrics.json
```

The final verifier never relies on a potentially modified test copy inside the agent workspace. Most tasks use a protected copy of the same fixed acceptance tests available in the task template. The hardest tasks use separate hidden holdout suites. This distinction matters: fixed tests are tamper-resistant, while only the latter are true holdouts.

## Mechanism and ablation

A four-arm analysis used the 20-run baseline and 20-run full-policy pools plus 12 Rule-1-only and 8 Rule-1-removed runs:

| Arm | Runs | Mean tokens | Distinct files read | Interpretation |
|---|---:|---:|---:|---|
| Baseline | 20 | 184,245 | 8.6 | No efficiency policy |
| Full policy | 20 | 149,092 | 4.9 | Largest overall token reduction |
| Rule 1 only | 12 | 171,385 | 5.2 | Reproduced nearly all file-read reduction |
| Rule 1 removed | 8 | 188,828 | 8.0 | Indistinguishable from baseline |

Minimal-context acquisition was therefore the main driver of narrower reading, while the complete five-rule policy produced the strongest overall token result. The remaining difference sits largely in the number of agent turns and cannot be cleanly attributed to one additional rule with the available sample.

## Reproduce the released results

Recomputing the headline statistics requires only Python 3 and the archived metrics—no model API or agent CLI:

```bash
python3 experiments/reproduce_key_results.py
```

The script:

1. audits all 230 archived metric files;
2. excludes the four runs marked `CONTAMINATED.md`;
3. checks that all 226 retained runs passed verification;
4. rebuilds the 20-vs.-20 OpenCode comparison; and
5. rebuilds the six-task stratified open-source result.

To launch a new OpenCode + GLM-5.2 trial, place the workspace outside this repository so OpenCode cannot discover the repository-level skill in a baseline arm:

```bash
python3 experiments/run_opencode_experiment.py \
  --task experiments/tasks/f1_deep_chain \
  --condition baseline \
  --run-id demo1 \
  --runs-dir /tmp/token-efficient-runs
```

## Repository map

| Path | Contents |
|---|---|
| [`.claude/skills/token-efficient-coding/`](.claude/skills/token-efficient-coding/) | Deployable five-rule skill |
| [`docs/`](docs/) | English study design, research report, and literature review |
| [`experiments/`](experiments/) | Runners, analyzers, task fixtures, archived trajectories, and metrics |
| [`experiments/reproduce_key_results.py`](experiments/reproduce_key_results.py) | One-command audit and headline-result reproduction |
| [`reports/opencode_glm_feasibility.md`](reports/opencode_glm_feasibility.md) | English feasibility note for the OpenCode harness |
| [`reports/zcode_glm_feasibility.md`](reports/zcode_glm_feasibility.md) | English feasibility note for ZCode |

Archived transcripts and third-party task fixtures are preserved verbatim for reproducibility. A small number contain non-English model output or upstream Unicode test strings; they are raw experimental data, not project documentation.

## Limitations

- The positive result is specific to one agent–model stack: OpenCode + GLM-5.2.
- The evaluated tasks are bug fixes; feature development and architectural refactoring were not tested.
- The open-source benchmark contains six historical Python bugs, not a broad population of repositories or languages.
- All evaluated runs passed, so the study found no pass-rate loss but could not estimate behavior on tasks that exceed the agents' capability ceiling.
- Token accounting differs across harnesses; cross-harness comparisons use within-harness treatment effects rather than absolute totals.

## License

MIT © Enze Zhang. See [`LICENSE`](LICENSE).
