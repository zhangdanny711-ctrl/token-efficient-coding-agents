#!/usr/bin/env python3
"""Run one OpenCode experiment trial: task -> opencode run -> transcript -> verify -> metrics.

Usage:
    python3 run_opencode_experiment.py --task tasks/smoke --condition baseline --run-id oc1
    python3 run_opencode_experiment.py --task tasks/smoke --condition skill --run-id oc1

Sibling of run_experiment.py (Claude Code) — same task layout, same verify.sh,
same metrics.json schema. Differences:

  - Agent: `opencode run --format json --auto`, default model zai-coding-plan/glm-5.2.
  - Skill injection: OpenCode has no .claude/skills/ mechanism. In `skill`
    condition the SKILL.md rule body is written to <workspace>/AGENTS.md
    (OpenCode's official project-instruction file, loaded into context
    automatically). The prompt is IDENTICAL between conditions — unlike the
    Claude Code arm, which appends an explicit "use the skill" line. This is
    a protocol difference; results are not comparable across arms.
  - Analyzer: analyze_opencode_trajectory.analyze (same output schema).
  - Run dirs are prefixed `oc_` so OpenCode runs never collide with existing
    Claude Code runs in experiments/runs/.

ZHIPU_API_KEY is taken from the environment; if unset, it is recovered from
~/.bashrc (the key line sits below the interactivity guard, so non-interactive
shells never see it via sourcing).
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
PROJECT_ROOT = EXPERIMENTS_DIR.parent
SKILL_SRC = PROJECT_ROOT / ".claude" / "skills" / "token-efficient-coding" / "SKILL.md"

DEFAULT_MODEL = "zai-coding-plan/glm-5.2"

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


def skill_agents_md():
    """SKILL.md body (frontmatter stripped) as AGENTS.md content."""
    text = SKILL_SRC.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    if m:
        text = text[m.end():]
    return text.lstrip("\n")


def build_workspace(task_dir: Path, run_dir: Path, condition: str) -> Path:
    workspace = run_dir / "workspace"
    shutil.copytree(
        task_dir / "repo", workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    if condition == "skill":
        (workspace / "AGENTS.md").write_text(skill_agents_md(), encoding="utf-8")
    return workspace


def run_agent(workspace: Path, prompt: str, model: str, timeout_s: int,
              transcript_path: Path) -> dict:
    # --dir is REQUIRED: without it OpenCode resolves a project root above
    # the workspace (no .git here) and the agent escapes into the frozen
    # task repo. --dir also scopes AGENTS.md loading to the workspace.
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
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=900, help="agent timeout (s)")
    ap.add_argument("--runs-dir", type=Path, default=EXPERIMENTS_DIR / "runs")
    args = ap.parse_args()

    task_dir = args.task.resolve()
    task_name = task_dir.name
    run_dir = args.runs_dir / f"oc_{task_name}_{args.condition}_{args.run_id}"
    if run_dir.exists():
        sys.exit(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True)

    if args.condition == "skill" and not SKILL_SRC.exists():
        sys.exit(f"skill file not found: {SKILL_SRC}")

    prompt = (task_dir / "task.md").read_text(encoding="utf-8")

    workspace = build_workspace(task_dir, run_dir, args.condition)
    transcript_path = run_dir / "transcript.ndjson"

    print(f"[oc/{task_name}/{args.condition}/{args.run_id}] running agent "
          f"(model={args.model}, timeout={args.timeout}s)...")
    try:
        agent_result = run_agent(workspace, prompt, args.model, args.timeout,
                                 transcript_path)
    except subprocess.TimeoutExpired:
        agent_result = {"exit_code": None, "stderr_tail": "TIMEOUT"}

    print(f"[oc/{task_name}/{args.condition}/{args.run_id}] verifying...")
    verification = run_verification(task_dir, workspace)

    metrics = analyze(transcript_path)
    record = {
        "task": task_name,
        "condition": args.condition,
        "run_id": args.run_id,
        "agent_cli": "opencode",
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
    print(f"[oc/{task_name}/{args.condition}/{args.run_id}] {status} | "
          f"tokens={total:,} (output={out:,}) | tool_calls={calls} | "
          f"-> {metrics_path}")


if __name__ == "__main__":
    main()
