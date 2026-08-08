#!/usr/bin/env python3
"""Run one experiment trial: task -> claude -p -> transcript -> verify -> metrics.

Usage:
    python3 run_experiment.py --task tasks/smoke --condition baseline --run-id 1
    python3 run_experiment.py --task tasks/smoke --condition skill --run-id 1

Each trial gets a fresh workspace (copy of the task's repo/). In `skill`
condition the token-efficient-coding SKILL.md is copied into the workspace's
.claude/skills/ and the prompt explicitly names it; in `baseline` the workspace
has no skill directory. Everything else (model, permissions, task card, repo
state) is identical between conditions.

Task directory layout:
    tasks/<name>/task.md     task card given to the agent (same for both arms)
    tasks/<name>/repo/       frozen repo state copied into the workspace
    tasks/<name>/verify.sh   holdout check: `bash verify.sh <workspace>` -> exit 0/1
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENTS_DIR.parent
SKILL_SRC = PROJECT_ROOT / ".claude" / "skills" / "token-efficient-coding" / "SKILL.md"

SKILL_INVOCATION = (
    "\n\nUse the token-efficient-coding skill while working on this task."
)

sys.path.insert(0, str(EXPERIMENTS_DIR))
from analyze_trajectory import analyze  # noqa: E402


def build_workspace(task_dir: Path, run_dir: Path, condition: str) -> Path:
    workspace = run_dir / "workspace"
    shutil.copytree(
        task_dir / "repo", workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    if condition == "skill":
        skill_dst = workspace / ".claude" / "skills" / "token-efficient-coding"
        skill_dst.mkdir(parents=True)
        shutil.copy(SKILL_SRC, skill_dst / "SKILL.md")
    return workspace


def run_agent(workspace: Path, prompt: str, model: str, timeout_s: int,
              transcript_path: Path) -> dict:
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    with open(transcript_path, "w", encoding="utf-8") as out:
        proc = subprocess.run(
            cmd, cwd=workspace, stdout=out, stderr=subprocess.PIPE,
            text=True, timeout=timeout_s,
        )
    return {"exit_code": proc.returncode, "stderr_tail": proc.stderr[-2000:]}


def run_verification(task_dir: Path, workspace: Path) -> dict:
    verify = task_dir / "verify.sh"
    proc = subprocess.run(
        ["bash", str(verify), str(workspace)],
        capture_output=True, text=True, timeout=300,
    )
    return {
        "passed": proc.returncode == 0,
        "output_tail": (proc.stdout + proc.stderr)[-2000:],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, type=Path,
                    help="task directory (contains task.md, repo/, verify.sh)")
    ap.add_argument("--condition", required=True, choices=["baseline", "skill"])
    ap.add_argument("--run-id", required=True, help="trial index, e.g. 1")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--timeout", type=int, default=900, help="agent timeout (s)")
    ap.add_argument("--runs-dir", type=Path, default=EXPERIMENTS_DIR / "runs")
    args = ap.parse_args()

    task_dir = args.task.resolve()
    task_name = task_dir.name
    run_dir = args.runs_dir / f"{task_name}_{args.condition}_{args.run_id}"
    if run_dir.exists():
        sys.exit(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True)

    if args.condition == "skill" and not SKILL_SRC.exists():
        sys.exit(f"skill file not found: {SKILL_SRC}")

    prompt = (task_dir / "task.md").read_text(encoding="utf-8")
    if args.condition == "skill":
        prompt += SKILL_INVOCATION

    workspace = build_workspace(task_dir, run_dir, args.condition)
    transcript_path = run_dir / "transcript.jsonl"

    print(f"[{task_name}/{args.condition}/{args.run_id}] running agent "
          f"(model={args.model}, timeout={args.timeout}s)...")
    try:
        agent_result = run_agent(workspace, prompt, args.model, args.timeout,
                                 transcript_path)
    except subprocess.TimeoutExpired:
        agent_result = {"exit_code": None, "stderr_tail": "TIMEOUT"}

    print(f"[{task_name}/{args.condition}/{args.run_id}] verifying...")
    verification = run_verification(task_dir, workspace)

    metrics = analyze(transcript_path)
    record = {
        "task": task_name,
        "condition": args.condition,
        "run_id": args.run_id,
        "model": args.model,
        "agent": agent_result,
        "verification": verification,
        "metrics": metrics,
    }
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    status = "PASS" if verification["passed"] else "FAIL"
    total = metrics["tokens"]["grand_total"]
    out = metrics["tokens"]["total"]["output_tokens"]
    calls = metrics["tool_calls"]["total"]
    print(f"[{task_name}/{args.condition}/{args.run_id}] {status} | "
          f"tokens={total:,} (output={out:,}) | tool_calls={calls} | "
          f"-> {metrics_path}")


if __name__ == "__main__":
    main()
