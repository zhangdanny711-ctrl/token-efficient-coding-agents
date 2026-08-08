INVALID RUN — do not use in analysis.

OpenCode auto-discovered the project-level .claude/skills/token-efficient-coding
(workspace lived under the project tree), exposed it as a `skill` tool, and the
baseline agent invoked it in the F3 runs (and had it visible in all four).
Baseline arm therefore contaminated by the skill under test.

Replaced by oc_*_occlean* runs executed with --runs-dir /tmp/oc_cal_runs
(outside the project tree). See reports/opencode_calibration_f1_f3.md.
