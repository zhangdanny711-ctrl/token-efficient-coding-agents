# Experiment Results Summary

Validation set, 2026-08-06. Model `claude-sonnet-5`, Claude Code headless
(`claude -p`), fresh session per trial. Authoritative batch: **run-id `v2`**
(run-id `v1` had a harness contamination bug, kept for the methodology note
in Observations §5).

## Task Overview

| Task | Type | Difficulty | Description |
|---|---|---|---|
| t1a_daterange | bug fix | T1 simple | off-by-one in `date_range` (single file, failing tests point at it) |
| t1b_slugify | bug fix | T1 simple | regex misses `+` quantifier; misleading comment claims runs are collapsed |
| t2a_ledger | bug fix | T2 multi-file | two independent bugs in two modules (`filters.py`, `summary.py`) |
| t2b_eventbus | feature | T2 multi-file | add `subscribe_once` to `EventBus` + expose through `LoggingBus` wrapper |
| t3a_pipeline | bug fix | T3 exploration | shallow `deep_merge` in `utils.py`; symptom (KeyError) appears in renderers, 7-module package |

## Results (run-id v2, 1 run per cell)

| Task | Condition | Success | Total tokens | Cache read | Cache write | Output | Tool calls | Time (s) | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| t1a_daterange | baseline | PASS | 156,117 | 142,776 | 12,677 | 654 | 4 | 16.7 | grep → read → edit → pytest, no waste |
| t1a_daterange | skill | PASS | 195,351 | 180,293 | 14,383 | 664 | 5 | 18.8 | identical path + Skill-launch turn |
| t1b_slugify | baseline | PASS | 156,553 | 143,195 | 12,824 | 524 | 4 | 14.8 | not fooled by misleading comment |
| t1b_slugify | skill | PASS | 196,487 | 181,040 | 14,727 | 709 | 5 | 19.2 | same fix, same path |
| t2a_ledger | baseline | PASS | 192,064 | 177,406 | 13,817 | 829 | 8 | 20.1 | read 4 files (incl. 2 not strictly needed) |
| t2a_ledger | skill | PASS | 232,053 | 215,792 | 15,237 | 1,011 | 7 | 23.8 | read only the 2 buggy files |
| t2b_eventbus | baseline | PASS | 200,489 | 182,705 | 15,829 | 1,943 | 9 | 28.5 | read 5 files including both test files |
| t2b_eventbus | skill | PASS | 237,842 | 219,553 | 16,655 | 1,621 | 8 | 27.1 | read 3 files; less narration (-322 output) |
| t3a_pipeline | baseline | PASS | 191,487 | 176,848 | 13,678 | 949 | 5 | 20.6 | traced KeyError to deep_merge quickly |
| t3a_pipeline | skill | PASS | 271,590 | 253,455 | 16,691 | 1,429 | 8 | 35.4 | +2 turns; one redundant re-verify round |

Paired deltas (skill − baseline), total tokens:
t1a **+39k**, t1b **+40k**, t2a **+40k**, t2b **+37k**, t3a **+80k**.
Quality: **10/10 PASS in both arms — no quality difference to trade against.**

## Rule-level behavior (v2)

| Rule | Indicator | Baseline | Skill | Verdict |
|---|---|---|---|---|
| R1 search-before-read | rate | 1.0 all tasks | 1.0 all tasks | **floor effect** — baseline already does this |
| R1 repeated reads | count | 0 all tasks | 0 all tasks | floor effect |
| R1 long outputs (>4k chars) | count | 0 all tasks | 0 all tasks | floor effect (repos too small to produce long output) |
| R1 reads per task (T2) | count | t2a: 4, t2b: 5 | t2a: 2, t2b: 3 | **skill visibly reduced reads** — the one clear R1 effect |
| R2 subagent usage | Task calls | 0 | 0 | not triggered — correct per its own ≥3-file exception; tasks too small |
| R3 no-progress iterations | repeated actions / repeated errors | 0 / 0 | 0 / ≤1 | not exercised — no run got stuck |
| R4 first-edit timing | turns before first Edit | 2–3 | 3–5 | skill arm looks slower, but ~1 turn is the Skill-launch turn itself; adjusted, timing is equal |
| R4 narrow test first | bool | false all | false all | **not followed by either arm** — both run full `pytest tests/` immediately (defensible: suites have 5–7 tests) |
| R5 Edit vs Write | writes on existing files | 0 | 0 | floor effect |
| R5 report length | assistant text chars | 182–583 | 117–692 | mixed; t2b −36%, t3a +13% |

## Observations

### 1. Skill did change trajectories, but only where baseline had slack
On both T2 tasks the skill arm read fewer files (t2a: 2 vs 4; t2b: 3 vs 5) —
exactly the Rule 1 behavior we wanted. On T1 tasks the baseline trajectory was
already minimal (grep → 1 read → 1 edit → pytest), so there was nothing for the
skill to remove.

### 2. Token result is a consistent INCREASE (+37–80k), and the overhead is structural
Decomposition of the ~+39k constant delta on T1/T2:
- the `Skill` tool invocation adds a full agent turn, and every extra turn
  re-reads the whole ~180k cached context (cache_read is the dominant field);
- SKILL.md itself adds ~1.7–2k to cache_creation;
- output overhead is small (±few hundred tokens).

So on tasks this small, **fixed skill overhead > removable waste**. t3a doubled
the delta (+80k) because the skill arm spent 2 extra turns, one of them a
redundant re-verification round.

Caveat: in raw dollars the picture is milder (cache reads are ~10× cheaper than
fresh input) — cost deltas were +$0.01–0.04 — but by our own token-first metric
definition, v1 on this task set is a net negative.

### 3. Which rules never got exercised
R2 (delegation) and R3 (stop rule) were never triggered in either arm. This is
a **task-set limitation, not evidence the rules work or don't**: repos are 5–8
files, nothing produces long output, and no run ever got stuck. The validation
set validates the pipeline and the easy half of R1/R4/R5; it cannot measure the
rules that target the biggest documented waste (loops, exploration bloat).

### 4. Where baseline wasted (what a harder benchmark must amplify)
The only baseline waste observed: reading files adjacent to but not needed for
the fix (t2a read `models.py`/`__init__.py`; t2b read both test files whole).
That is real Rule-1 slack, worth ~2–3 reads ≈ a few k tokens — an order of
magnitude smaller than the skill's own overhead on these tasks. For the full
benchmark, tasks need: bigger repos (50+ files), commands that produce long
outputs, and at least one task designed to induce a debugging loop (flaky
assumption, misleading error). Otherwise the experiment measures overhead, not
optimization.

### 5. Methodology lesson from the discarded v1 batch
In v1, task authoring left `__pycache__` dirs inside `tasks/*/repo/`; copied
into workspaces, stale bytecode made pytest fail with import errors *after* the
agent's correct fix. The t1b skill run burned +180k tokens debugging our
contamination (it did debug systematically — ls, find, clean, retry — no rule
violation). Fixes: `copytree(..., ignore=__pycache__)` in the runner and purged
task dirs. v2 numbers are clean; v1 kept in `runs/` as a cautionary artifact.

### 6. Honest summary for the report
On small, clean, single-bug tasks with a strong model, the baseline is already
near token-optimal; a policy skill can only add overhead there. The interesting
question for the full benchmark is whether the T2-style read reduction and the
untested R2/R3 rules outweigh the fixed overhead once tasks are large and noisy
enough to have real waste. This validation run neither proves nor refutes the
skill — it bounds where it can possibly pay off.
