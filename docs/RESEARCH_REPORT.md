# Research Report

## Executive summary

This project evaluated a five-rule prompt-level policy for completing coding tasks with less context waste. The same policy produced different economic outcomes across agent–model environments.

On OpenCode + GLM-5.2, the policy reduced mean total tokens by 19.1% in a controlled 20-vs.-20 comparison and reduced task-level token use by 36.1% across six historical open-source bugs. All 88 runs in those two headline evaluations passed their authoritative tests.

On Claude Code + Sonnet, a calibration gate found almost no target behavioral waste: the baseline already searched before reading, limited large-file reads, truncated command output, and avoided repeated actions. The planned large skill arm was therefore stopped. An earlier five-task validation showed that explicit skill invocation added a full turn and increased total tokens by 37,000–80,000 on tasks with little removable waste.

The central conclusion is conditional: prompt-level efficiency rules are valuable when the baseline agent leaves behavioral waste, but can become overhead when the harness already supplies the same discipline.

## Released data audit

| Item | Count |
|---|---:|
| Archived `metrics.json` files | 230 |
| Explicitly contaminated and excluded | 4 |
| Valid archived runs | 226 |
| Valid runs passing configured verification | 226 |

The four excluded OpenCode baseline runs were executed under the repository tree. OpenCode discovered the project-level skill through parent-directory traversal, contaminating the control arm. The issue was documented, the default run location was moved outside the repository, and the runs were replaced.

## Claude Code calibration

### Small-task validation

Five task fixtures were each run once under baseline and skill conditions. Both conditions passed all tasks. Baseline trajectories were already short and disciplined; policy invocation usually added one complete turn.

| Task | Baseline tokens | Skill tokens | Delta |
|---|---:|---:|---:|
| Date range | 156,117 | 195,351 | +39,234 |
| Slugify | 156,553 | 196,487 | +39,934 |
| Ledger | 192,064 | 232,053 | +39,989 |
| Event bus | 200,489 | 237,842 | +37,353 |
| Pipeline | 191,487 | 271,590 | +80,103 |

The first four deltas are close to a fixed invocation cost. The pipeline skill run used two additional turns, producing the larger increase.

### F1/F3 expansion gate

The larger F1 and F3 tasks were run baseline-only, twice per task, as specified by the expansion gate. They did not exhibit the required waste:

- F1 used search to cross a multi-module call chain and read only narrow ranges from a 688-line file.
- F3 avoided a 25,000-character log path and used concise test output instead.
- repeated reads and identical-action loops remained at zero.

Because the baseline did not leave enough target waste to offset policy invocation, the skill arm for these tasks was not launched.

## OpenCode main result

The main experiment pooled 20 baseline and 20 full-policy runs over F1 and F3 under OpenCode + GLM-5.2.

| Metric | Baseline | Full policy | Relative change | p-value |
|---|---:|---:|---:|---:|
| Mean total tokens | 184,245 | 149,092 | **−19.1%** | **0.0094** |
| Median total tokens | — | — | −30.5% | — |
| Mean distinct files read | 8.6 | 4.9 | **−43%** | 0.00014 |
| Mean long outputs | 3.8 | 2.2 | **−42%** | 0.00068 |
| Pass rate | 20/20 | 20/20 | no difference | — |

Unlike Claude Code, OpenCode's baseline exhibited broad, enumerative reading. The policy reduced the width of exploration while keeping task outcomes unchanged.

## Historical open-source bugs

Authored tasks create author-circularity risk: the same researcher designs both the intervention and the benchmark. To test external validity, 26 candidate fix commits were mechanically screened from Python libraries and six were selected as tasks.

| Task | Library | Baseline median | Skill median | Relative change |
|---|---|---:|---:|---:|
| `eco_e1_tinydb_nextid` | TinyDB | 140,667 | 80,374 | −42.9% |
| `eco_e2_tabulate_sepline` | Tabulate | 960,826 | 848,743 | −11.7% |
| `eco_e4_boltons_omdeq` | Boltons | 126,485 | 56,340 | −55.5% |
| `eco_e5_tinydb_emptylen` | TinyDB | 110,848 | 70,320 | −36.6% |
| `eco_e6_moreit_sliced` | more-itertools | 79,643 | 60,331 | −24.2% |
| `eco_e7_funcy_autocurry` | Funcy | 243,531 | 131,537 | −46.0% |

Each task used four baseline and four policy runs. The equal-task-weighted average of within-task median deltas was **−36.1%** (`p=0.0003`), with the same direction on all six tasks. All 48 runs passed.

The result was larger, not smaller, than the lab effect. Real repositories supplied natural exploration surfaces—documentation, neighboring modules, and legacy structure—without synthetic token amplifiers.

## Rule-level ablation

The four-arm analysis combined the main 20 baseline and 20 full-policy runs with 12 Rule-1-only and 8 Rule-1-removed runs.

| Arm | Mean tokens | Relative to baseline | Mean files read | Relative to baseline |
|---|---:|---:|---:|---:|
| Baseline | 184,245 | — | 8.6 | — |
| Full policy | 149,092 | −19.1% | 4.9 | −43% |
| Rule 1 only | 171,385 | −7% | 5.2 | −40% |
| Rule 1 removed | 188,828 | +2.5% | 8.0 | −7% |

Rule 1 alone reproduced nearly all of the file-read reduction, while removing it returned behavior to baseline. The complete policy still produced the largest token reduction. The residual difference correlates with fewer turns under the complete policy, but the study cannot distinguish rule interaction from sampling variance.

## Turn fragmentation

Trajectory reconstruction found that 61–68% of token use sat behind turn boundaries that were theoretically mergeable. A dedicated batching instruction changed command-grouping behavior but did not reduce total tokens. This suggests that some fragmentation is a generation habit that a single prompt rule cannot reliably eliminate.

The OpenCode cost structure amplifies turns: each additional turn re-sends the accumulated history. Narrower reads reduce the amount added per turn; controlling the number of turns remains a separate problem.

## Quality stress test

The study progressively removed diagnostic information from three difficult tasks:

1. failing tests were visible;
2. only a reproduction path was supplied; and
3. only a prose symptom was supplied, with hidden holdout tests.

Baseline runs passed 36/36 across the three levels. At the hardest level, an additional 12 full-policy runs also passed, producing 48/48 passes across the stress archive. Less task information increased token use by 2.8–4.2× and increased turns from roughly 11 to as many as 32, but did not cause broader file reading.

The hardest-tier policy comparison produced an exploratory **−38.8%** stratified-median token effect (`p=0.01`) with 12/12 passes in both conditions. Because this is only four runs per condition per task, it should be treated as a promising secondary finding rather than the primary estimate.

## Interpretation

The policy controls what enters context more reliably than it controls how many turns the agent takes. Its strongest causal evidence concerns file-read width:

- search-before-read and narrow inspection are prompt-reachable;
- turn granularity is only weakly prompt-reachable; and
- per-turn history replay is a harness-level structural cost.

A deployment decision should begin with two or more baseline calibration runs. If the baseline already avoids wide reads, repeated reads, long unfiltered outputs, and unproductive loops, policy injection may not pay. If those behaviors are present and policy injection is cheap, the full skill is a reasonable default.

## Limitations

1. The statistically positive result uses one model–harness combination.
2. All evaluated tasks are bug fixes in Python repositories.
3. The real-bug study includes six historical commits from five libraries.
4. The stress tasks did not lower pass rate, so failure behavior beyond this difficulty ceiling remains unknown.
5. Cross-harness token totals are not directly comparable because accounting and injection protocols differ.
6. Rule 2 cannot be exercised in OpenCode without a subagent facility, and several lure tasks failed to trigger the intended Rule 3/Rule 4 behaviors.

## Reproduction

Run:

```bash
python3 experiments/reproduce_key_results.py
```

The script audits the archive and rebuilds the two headline positive results from released metrics.
