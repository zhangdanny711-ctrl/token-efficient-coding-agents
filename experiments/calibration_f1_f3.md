# Calibration Pilot: F1 + F3 (baseline ×2)

2026-08-06. Model `claude-sonnet-5`, Claude Code headless, fresh session
per trial. Per design/03 §6: build only F1 (Alpha deep-chain) and F3
(Beta long-log), run baseline ×2 each, and check the pass line before
authorizing the remaining 6 tasks.

## Pass line (pre-registered)

1. baseline total tokens ≥ 300k, AND
2. target waste behavior appears ≥1×:
   - F1: whole-reads of ≥3 large modules along the call chain
   - F3: ≥1 long_output (>4k chars) collected into main context

## Results

| Run | Success | Total tokens | Cache read | Cache write | Output | Tool calls | Time (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| f1 baseline p1 | PASS | 243,358 | 204,541 | 37,318 | 1,485 | 6 | 31.6 |
| f1 baseline p2 | PASS | 282,209 | 253,555 | 26,995 | 1,645 | 6 | 29.3 |
| f3 baseline p1 | PASS | 308,178 | 288,987 | 17,603 | 1,570 | 8 | 38.4 |
| f3 baseline p2 | PASS | 270,898 | 252,429 | 16,922 | 1,531 | 7 | 34.5 |

**Verdict: FAIL the pass line → early stop triggered.**

- Tokens: 3 of 4 runs below 300k (243k–308k; the one ≥300k is marginal).
- Target waste: **zero occurrences in all 4 runs.**

## Observed trajectories (why the amplifiers never fired)

**F1 (deep-chain, big files).** Both runs: `find` → read `money.py` →
grep for Decimal/serialization patterns → read `serializers.py` (one of
the two reads used offset/limit) → single Edit → `pytest tests/ -q 2>&1
| tail -20`. Only **2 distinct files read**, 6 tool calls, first-try fix.
The failing test names (`test_serializers.py`) in the pytest tail gave
the location away; the 3-layer symptom-to-cause gap was bridged by one
grep, not by walking the call chain.

**F3 (long-log, 25k-char run command).** Both runs: the agent **never
ran the long-log command at all.** It went straight to
`pytest tests/ -q 2>&1 | tail -80`, read the spec + `numbers.py`
(grep-guided), fixed `parse_decimal`, re-ran pytest with `| tail -20`.
`long_outputs = 0` in both runs — the 25k-char amplifier was available
but never triggered, because task.md offered pytest as a repro and the
agent self-tails every command.

## Interpretation

This is the outcome design/03 §6 pre-registered as the early-stop
branch: *"若 baseline 在这种规模下依然纪律良好 → skill 假说在该模型上
基本可判负，以 2 个任务的成本提前止损；写入报告即为有效结论。"*

Concretely, `claude-sonnet-5` under Claude Code already exhibits, by
default, the exact behaviors Skill v1's rules prescribe:

- **R1 (minimal reads / filtered logs):** it self-appends `| tail -N`
  to every test/run command and greps before reading; it never collected
  a long output even when a 25k-char log was the advertised repro path.
- **R2 (delegation):** unnecessary — exploration cost was 1 grep, so
  there was nothing to delegate.
- **R3/R4:** first-try fixes, no loops, 6–8 tool calls, `turns_before_
  first_edit` 4–6 regardless of repo size.

The remaining token mass is cache re-reads of an efficient trajectory
(~1.5k output tokens per run), which is exactly the fixed-overhead
regime where adding a skill turn costs ~+40k and can only lose.

Two honest caveats, and why they don't change the verdict:

1. *Amplifiers could be made crueller* (no pytest repro in task.md,
   failing tests that don't name the culprit file, log-only symptoms).
   But at that point we would be constructing tasks that defeat the
   model's default discipline specifically to give the skill room —
   the benchmark would measure our task design, not the skill.
2. *n=2 per task.* Variance across the 4 runs is small (σ ≈ 25k) and
   behavior is qualitatively identical in all 4 trajectories; more runs
   would not move a zero-occurrence waste count meaningfully.

## Decision

Stop benchmark expansion (F2, F4–F8 not built). The negative result is
the finding:

> **For claude-sonnet-5 under Claude Code, prompt-level token-efficiency
> rules (Skill v1) are dominated by the harness/model's built-in
> discipline on realistic single-bug tasks up to ~300k-token scale.
> The skill's fixed invocation overhead (~+40k tokens) has no
> recoverable waste to offset — including on tasks purpose-built with
> waste amplifiers (large files, deep call chains, 25k-char logs).**

Artifacts kept for the report: 2 synthetic repos (alpha_storefront:
56 files / 5,453 LOC / 371 tests; beta_etlkit: 39 files / ~2.3k LOC /
122 tests + deterministic ~25k-char run log), F1/F3 task definitions
with holdout verify, and 4 baseline trajectories.
