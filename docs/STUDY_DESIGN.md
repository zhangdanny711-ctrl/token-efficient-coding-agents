# Study Design

## Research question

How much of a multi-turn coding agent's token use can be reduced by a user-level behavioral policy while preserving task completion quality?

The intervention is a five-rule `SKILL.md`. It changes neither model weights nor agent-harness internals. The study therefore measures the portion of token use reachable from the prompt layer.

## Systems under evaluation

| Agent harness | Model | Skill injection | Role in the study |
|---|---|---|---|
| Claude Code | Claude Sonnet | Explicit skill invocation | Strong-baseline calibration and early stop |
| OpenCode | GLM-5.2 | Workspace `AGENTS.md` | Main controlled experiments and external-validity studies |

The systems differ in both model and harness. Cross-system findings are treated as environment comparisons, not as a clean causal estimate of either the model or harness alone.

## Intervention

The complete policy contains five rules:

1. minimal context acquisition;
2. delegated exploration when the search space is genuinely wide;
3. progress tracking and termination of unproductive paths;
4. effort and verification scaled to task complexity; and
5. concise, targeted edits and reporting.

The exact released text is [the token-efficient coding skill](../.claude/skills/token-efficient-coding/SKILL.md).

## Conditions

- **Baseline:** the agent receives the task and repository without the policy.
- **Full policy:** the same task and repository plus the complete five-rule policy.
- **Rule 1 only:** only minimal-context acquisition is injected.
- **Rule 1 removed:** Rules 2–5 are injected without Rule 1.

Within an experiment, task prompt, repository snapshot, model, runner, timeout, and verifier are held fixed. Runs start in fresh workspaces.

## Run lifecycle

1. Copy the frozen task repository into a unique run directory.
2. Inject the assigned policy condition.
3. launch the coding agent headlessly with the task card as its prompt.
4. Capture the complete JSON/NDJSON trajectory.
5. Derive token, turn, file-read, long-output, tool-use, and progress metrics.
6. Re-test the agent-modified source with the task's authoritative verifier.
7. Store the trajectory and `metrics.json`; omit the disposable workspace from release archives.

OpenCode workspaces must live outside the project tree. OpenCode searches parent directories for `.claude/skills/`; keeping workspaces inside the repository caused four early baseline runs to discover the treatment. Those runs are marked `CONTAMINATED.md`, excluded, and replaced.

## Verification

The verifier is outside the agent's run workspace.

For most lab and ecological-validity tasks, it creates a clean temporary directory, copies in the agent-modified source package, and pairs it with a protected copy of the fixed acceptance tests. The agent may see an equivalent test copy in its workspace, but edits to that copy cannot change final scoring.

The hardest underspecified tasks use separate holdout suites that are not included in the agent workspace. Those are true hidden tests.

Historical-bug tasks are validated in both directions before use:

- the parent snapshot plus the new regression test must fail; and
- applying the official fix commit must make it pass.

## Experiment sequence

| Stage | Purpose | Design |
|---|---|---|
| Claude Code validation | Validate the runner and estimate policy overhead on small tasks | 5 tasks × 2 conditions |
| Claude Code calibration gate | Check whether larger tasks induce target waste before expanding | 2 tasks × 2 baseline runs; stopped before skill expansion |
| OpenCode calibration | Confirm target waste and validate skill injection | F1/F3 pilot runs |
| Main OpenCode comparison | Estimate the primary token effect | 20 baseline vs. 20 full-policy runs |
| Batching ablation | Test whether one batching instruction reduces turn fragmentation | 24 formal runs plus smoke |
| External-validity tasks | Probe small and multi-layer task behavior | 28 archived runs |
| Rule-level ablation | Attribute the effect to Rule 1 versus the full policy | 20 new runs plus 40 reused main-study runs |
| Historical OSS bugs | Test generalization beyond authored tasks | 6 tasks × 2 conditions × 4 runs = 48 |
| Difficulty-band stress test | Reduce task information and probe pass-rate risk | 48 runs across three tiers |

## Primary metrics

- **Total tokens:** fresh input, output, cache read, and cache write when reported by the harness.
- **Distinct files read:** number of unique source files inspected by the main agent.
- **Long outputs:** tool observations above the predefined character threshold.
- **Turns and tool calls:** trajectory length and action distribution.
- **Task completion:** verifier PASS/FAIL.

Absolute token accounting differs across harnesses. Treatment effects are therefore computed within a harness.

## Statistical analysis

The main 20-vs.-20 comparison uses a one-sided permutation test for lower mean total tokens under the policy. The historical-bug study computes a median within each task and then averages the six within-task relative deltas, preserving equal task weight. Its p-value comes from label permutations within each task stratum.

Monte Carlo permutation tests use fixed random seeds in the reproduction script. Effect sizes are deterministic from the archive; the final p-value digit may vary slightly with the requested number of permutations.

## Pre-registered decision rules

Calibration gates were used before expensive arm expansion. An experiment proceeded only if baseline runs both passed and exhibited the behavior the intervention was designed to change. This produced two notable early stops:

- Claude Code's baseline already performed narrow, hypothesis-driven exploration with no repeated reads or unproductive loops.
- Two authored lure tasks failed to induce their intended baseline behavior and were not expanded as originally proposed.

These decisions prevent spending additional runs on a treatment with no reachable target and reduce post-hoc selection of favorable tasks.
