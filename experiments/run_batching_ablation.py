#!/usr/bin/env python3
"""Batching-instruction prompt ablation: control vs treatment on OpenCode + GLM-5.2.

Usage:
    python3 run_batching_ablation.py --task tasks/f1_deep_chain --arm control   --run-id b1
    python3 run_batching_ablation.py --task tasks/f1_deep_chain --arm treatment --run-id b1

Design: docs/STUDY_DESIGN.md.

Arms:
    control    — no injection at all (identical to the OpenCode baseline arm).
    treatment  — workspace AGENTS.md contains ONLY the batching instruction
                 below. No Skill v1 content.

Everything else is identical to run_opencode_experiment.py (task layout,
workspace isolation, contamination guard, verify.sh, NDJSON transcript,
analyze_opencode_trajectory metrics). This is a separate sibling runner so
the existing benchmark files stay untouched.

Run dirs are prefixed `ba_` (batching ablation) to avoid any collision with
`oc_` benchmark runs. Default --runs-dir is OUTSIDE the project tree —
OpenCode auto-discovers .claude/skills/ up the directory tree, so ablation
workspaces must never live under the project (see docs/STUDY_DESIGN.md).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

BATCHING_INSTRUCTION = """\
Before acting, batch related information-gathering actions into the same turn \
whenever possible. Avoid splitting a single exploration objective across \
multiple turns when the required information can be collected together.
"""

DEFAULT_MODEL = "zai-coding-plan/glm-5.2"
DEFAULT_RUNS_DIR = Path("/tmp/oc_batching_ablation_runs")

sys.path.insert(0, str(EXPERIMENTS_DIR))
from analyze_opencode_trajectory import analyze  # noqa: E402


def resolve_api_key():
    key = os.environ.get("ZHIPU_API_KEY")
    if key:
        return key
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        m = re.search(r"^export ZHIPU_API_KEY=(\S+)", bashrc.read_text(), re.M)
        if m:
            return m.group(1)
    sys.exit("ZHIPU_API_KEY not set and not found in ~/.bashrc")


def check_repo_clean(task_dir: Path):
    """Contamination guard: refuse to run from a dirty frozen repo."""
    repo = task_dir / "repo"
    dirt = [p for p in repo.rglob("*")
            if p.name in ("__pycache__", ".pytest_cache") or p.suffix == ".pyc"]
    if dirt:
        sys.exit(f"frozen repo contaminated ({len(dirt)} cache artifacts), "
                 f"clean before running: {task_dir}")


def build_workspace(task_dir: Path, run_dir: Path, arm: str) -> Path:
    workspace = run_dir / "workspace"
    shutil.copytree(
        task_dir / "repo", workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    if arm == "treatment":
        (workspace / "AGENTS.md").write_text(BATCHING_INSTRUCTION, encoding="utf-8")
    return workspace


def run_agent(workspace: Path, prompt: str, model: str, timeout_s: int,
              transcript_path: Path) -> dict:
    cmd = [
        "opencode", "run", prompt,
        "--format", "json",
        "--auto",
        "-m", model,
        "--dir", str(workspace),
    ]
    env = dict(os.environ, ZHIPU_API_KEY=resolve_api_key())
    with open(transcript_path, "w", encoding="utf-8") as out:
        proc = subprocess.run(
            cmd, cwd=workspace, stdout=out, stderr=subprocess.PIPE,
            text=True, timeout=timeout_s, env=env,
        )
    return {"exit_code": proc.returncode, "stderr_tail": proc.stderr[-2000:]}


def run_verification(task_dir: Path, workspace: Path) -> dict:
    proc = subprocess.run(
        ["bash", str(task_dir / "verify.sh"), str(workspace)],
        capture_output=True, text=True, timeout=300,
    )
    return {
        "passed": proc.returncode == 0,
        "output_tail": (proc.stdout + proc.stderr)[-2000:],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, type=Path)
    ap.add_argument("--arm", required=True, choices=["control", "treatment"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    args = ap.parse_args()

    task_dir = args.task.resolve()
    task_name = task_dir.name
    run_dir = args.runs_dir / f"ba_{task_name}_{args.arm}_{args.run_id}"
    if run_dir.exists():
        sys.exit(f"refusing to overwrite existing run dir: {run_dir}")

    check_repo_clean(task_dir)
    run_dir.mkdir(parents=True)

    prompt = (task_dir / "task.md").read_text(encoding="utf-8")
    workspace = build_workspace(task_dir, run_dir, args.arm)
    transcript_path = run_dir / "transcript.ndjson"

    print(f"[ba/{task_name}/{args.arm}/{args.run_id}] running agent "
          f"(model={args.model}, timeout={args.timeout}s)...")
    try:
        agent_result = run_agent(workspace, prompt, args.model, args.timeout,
                                 transcript_path)
    except subprocess.TimeoutExpired:
        agent_result = {"exit_code": None, "stderr_tail": "TIMEOUT"}

    print(f"[ba/{task_name}/{args.arm}/{args.run_id}] verifying...")
    verification = run_verification(task_dir, workspace)

    metrics = analyze(transcript_path)
    turns = metrics["behavior"]["main_turns"]
    calls = metrics["tool_calls"]["total"]
    record = {
        "experiment": "batching_ablation",
        "task": task_name,
        "arm": args.arm,
        "run_id": args.run_id,
        "agent_cli": "opencode",
        "model": args.model,
        "density_calls_per_turn": round(calls / turns, 3) if turns else None,
        "agent": agent_result,
        "verification": verification,
        "metrics": metrics,
    }
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    status = "PASS" if verification["passed"] else "FAIL"
    total = metrics["tokens"]["grand_total"]
    print(f"[ba/{task_name}/{args.arm}/{args.run_id}] {status} | "
          f"tokens={total:,} | turns={turns} | calls={calls} "
          f"(density={record['density_calls_per_turn']}) | -> {metrics_path}")


if __name__ == "__main__":
    main()
