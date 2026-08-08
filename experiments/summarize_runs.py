#!/usr/bin/env python3
"""Aggregate metrics.json files under runs/ into comparison tables.

Usage: python3 summarize_runs.py [--runs-dir runs] [--exclude smoke]
"""

import argparse
import json
from pathlib import Path

TOKEN_FIELDS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


def load_records(runs_dir, exclude=()):
    records = []
    for mf in sorted(runs_dir.glob("*/metrics.json")):
        r = json.loads(mf.read_text())
        if any(r["task"].startswith(p) for p in exclude):
            continue
        records.append(r)
    return records


def row(r):
    m = r["metrics"]
    t = m["tokens"]["total"]
    b = m["behavior"]
    tc = m["tool_calls"]
    res = m.get("result", {})
    return {
        "task": r["task"],
        "cond": r["condition"],
        "run": r["run_id"],
        "pass": r["verification"]["passed"],
        "total_tokens": m["tokens"]["grand_total"],
        "input": t["input_tokens"],
        "cache_read": t["cache_read_input_tokens"],
        "cache_write": t["cache_creation_input_tokens"],
        "output": t["output_tokens"],
        "tool_calls": tc["total"],
        "reads": tc["Read"],
        "edits": tc["Edit"],
        "writes": tc["Write"],
        "bash": tc["Bash"],
        "task_tool": tc["Task"],
        "duration_s": round((res.get("duration_ms") or 0) / 1000, 1),
        "cost_usd": round(res.get("total_cost_usd") or 0, 4),
        # rule-level
        "r1_search_rate": b["search_before_read_rate"],
        "r1_repeat_reads": b["repeated_reads"],
        "r1_long_outputs": b["long_outputs"],
        "r3_repeat_actions": b["repeated_identical_actions"],
        "r3_max_err_repeat": b["max_identical_error_repeats"],
        "r4_turns_before_edit": b["turns_before_first_edit"],
        "r4_narrow_first": b["narrow_test_before_full"],
        "r5_text_chars": b["assistant_text_chars"],
        "turns": b["main_turns"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path,
                    default=Path(__file__).parent / "runs")
    ap.add_argument("--exclude", nargs="*", default=["smoke"])
    ap.add_argument("--run-id", help="only include runs with this run_id")
    args = ap.parse_args()

    records = load_records(args.runs_dir, args.exclude)
    if args.run_id:
        records = [r for r in records if r["run_id"] == args.run_id]
    rows = [row(r) for r in records]
    if not rows:
        print("no runs found")
        return

    cols = ["task", "cond", "pass", "total_tokens", "cache_read",
            "cache_write", "output", "tool_calls", "reads", "bash",
            "task_tool", "duration_s", "cost_usd"]
    print(" | ".join(cols))
    for r in sorted(rows, key=lambda x: (x["task"], x["cond"], x["run"])):
        print(" | ".join(str(r[c]) for c in cols))

    print()
    cols2 = ["task", "cond", "r1_search_rate", "r1_repeat_reads",
             "r1_long_outputs", "r3_repeat_actions", "r3_max_err_repeat",
             "r4_turns_before_edit", "r4_narrow_first", "r5_text_chars",
             "edits", "writes", "turns"]
    print(" | ".join(cols2))
    for r in sorted(rows, key=lambda x: (x["task"], x["cond"], x["run"])):
        print(" | ".join(str(r[c]) for c in cols2))

    # paired per-task deltas (skill - baseline), averaged over runs
    print()
    print("paired deltas (skill - baseline), positive = skill used more:")
    by_key = {}
    for r in rows:
        by_key.setdefault((r["task"], r["cond"]), []).append(r)
    tasks = sorted({r["task"] for r in rows})
    for task in tasks:
        base = by_key.get((task, "baseline"), [])
        skill = by_key.get((task, "skill"), [])
        if not base or not skill:
            continue
        def avg(rs, k):
            vals = [x[k] for x in rs if x[k] is not None]
            return sum(vals) / len(vals) if vals else 0
        dt = avg(skill, "total_tokens") - avg(base, "total_tokens")
        do = avg(skill, "output") - avg(base, "output")
        dc = avg(skill, "tool_calls") - avg(base, "tool_calls")
        print(f"  {task}: total {dt:+,.0f}, output {do:+,.0f}, "
              f"tool_calls {dc:+.1f}, "
              f"pass base={all(x['pass'] for x in base)} "
              f"skill={all(x['pass'] for x in skill)}")


if __name__ == "__main__":
    main()
