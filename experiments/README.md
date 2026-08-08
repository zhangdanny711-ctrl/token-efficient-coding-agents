# Experiment framework

Pipeline: task → `claude -p` (headless) → transcript JSONL → verify → metrics.

## Layout

```
experiments/
├── run_experiment.py      # one trial: build workspace, run agent, verify, analyze
├── analyze_trajectory.py  # transcript JSONL → token/tool/behavior metrics
├── tasks/
│   └── smoke/             # smoke test task (single-file bug fix)
│       ├── task.md        # task card given to the agent (identical in both arms)
│       ├── repo/          # frozen repo state, copied fresh per trial
│       └── verify.sh      # holdout check, run by harness after the agent exits
└── runs/                  # one dir per trial (gitignored candidate)
    └── <task>_<condition>_<run_id>/
        ├── workspace/     # the copy the agent worked in
        ├── transcript.jsonl
        └── metrics.json
```

## Running a trial

```bash
cd experiments
python3 run_experiment.py --task tasks/smoke --condition baseline --run-id 1
python3 run_experiment.py --task tasks/smoke --condition skill    --run-id 1
python3 analyze_trajectory.py runs/smoke_skill_1/transcript.jsonl          # re-print summary
python3 analyze_trajectory.py runs/smoke_skill_1/transcript.jsonl --json   # full metrics
```

Defaults: `--model claude-sonnet-5`, `--timeout 900`. Refuses to overwrite an
existing run dir.

## Conditions

- **baseline**: fresh workspace copy, no skill directory.
- **skill**: same workspace plus `.claude/skills/token-efficient-coding/SKILL.md`
  (copied from the project root at run time), and the task prompt gets one extra
  sentence explicitly invoking the skill. Everything else identical.

## Metrics (metrics.json)

- `tokens.total` — authoritative usage from the final `result` event
  (input / cache_read / cache_creation / output). Per-message sums are kept in
  `tokens.main` / `tokens.subagent` for main-vs-subagent attribution
  (note: per-event `output_tokens` are streaming snapshots and undercount;
  use `tokens.total` for totals).
- `tool_calls` — total and per-tool (Read/Edit/Write/Bash/Task), subagent calls
  counted separately.
- `behavior` — repeated reads of unmodified files, reads with offset/limit,
  turns before first Edit, tool results > 4000 chars ("long outputs"),
  main-context turn count.
- `verification.passed` — holdout `verify.sh` result (agent never sees it).

## Known caveats

- Skill-arm token totals include the SKILL.md injection overhead (by design).
- `verify.sh` must ignore `__pycache__`/`*.pyc` when diffing protected paths.
- One `claude -p` call = one fresh session; no state carries across trials.
