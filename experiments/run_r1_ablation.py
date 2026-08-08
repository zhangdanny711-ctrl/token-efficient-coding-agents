#!/usr/bin/env python3
"""R1-only rule ablation: which part of Skill v1 carries the token effect?

Usage:
    python3 run_r1_ablation.py --task tasks/f1_deep_chain --arm r1only    --run-id r1
    python3 run_r1_ablation.py --task tasks/f1_deep_chain --arm r1removed --run-id r1

Design: reports/opencode_study/r1_ablation_design.md.

Arms:
    r1only     — workspace AGENTS.md = SKILL.md title + intro + Rule 1, verbatim.
    r1removed  — workspace AGENTS.md = SKILL.md title + intro + Rules 2-5, verbatim.

Both texts are extracted verbatim from .claude/skills/token-efficient-coding/SKILL.md
at run time (no paraphrase drift). The Workflow section is excluded from both arms:
its step 5 embeds R3 and step 4 embeds R4, which would contaminate r1only.

Everything else is identical to run_opencode_experiment.py (task layout,
workspace isolation, contamination guard, verify.sh, NDJSON transcript,
analyze_opencode_trajectory metrics). Sibling runner; existing files untouched.

Run dirs are prefixed `r1_`. Default --runs-dir is OUTSIDE the project tree —
OpenCode auto-discovers .claude/skills/ up the directory tree, so ablation
workspaces must never live under the project (see opencode_calibration_f1_f3.md §0.2).
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
DEFAULT_RUNS_DIR = Path("/tmp/oc_r1_ablation_runs")

sys.path.insert(0, str(EXPERIMENTS_DIR))
from analyze_opencode_trajectory import analyze  # noqa: E402


def split_skill_sections():
    """Return (intro, {rule_number: rule_text}) from SKILL.md, verbatim.

    intro = everything from the '# Token-Efficient Coding' title up to (but
    excluding) the '## Workflow' heading. Rules keyed 1-5 by their heading.
    """
    text = SKILL_SRC.read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)  # strip frontmatter
    m = re.search(r"^(# Token-Efficient Coding\n.*?)(?=^## Workflow$)", body,
                  re.M | re.S)
    if not m:
        sys.exit("SKILL.md structure changed: intro/Workflow not found")
    intro = m.group(1).rstrip() + "\n"
    rules = {}
    for rm in re.finditer(
            r"^(## Rule (\d) — .*?)(?=^## Rule \d — |\Z)", body, re.M | re.S):
        rules[int(rm.group(2))] = rm.group(1).rstrip() + "\n"
    if sorted(rules) != [1, 2, 3, 4, 5]:
        sys.exit(f"SKILL.md structure changed: found rules {sorted(rules)}")
    return intro, rules


def agents_md_for(arm: str) -> str:
    intro, rules = split_skill_sections()
    if arm == "r1only":
        return intro + "\n" + rules[1]
    return intro + "\n" + "\n".join(rules[n] for n in (2, 3, 4, 5))


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
    (workspace / "AGENTS.md").write_text(agents_md_for(arm), encoding="utf-8")
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
    ap.add_argument("--arm", required=True, choices=["r1only", "r1removed"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    args = ap.parse_args()

    task_dir = args.task.resolve()
    task_name = task_dir.name
    run_dir = args.runs_dir / f"r1_{task_name}_{args.arm}_{args.run_id}"
    if run_dir.exists():
        sys.exit(f"refusing to overwrite existing run dir: {run_dir}")

    check_repo_clean(task_dir)
    run_dir.mkdir(parents=True)

    prompt = (task_dir / "task.md").read_text(encoding="utf-8")
    workspace = build_workspace(task_dir, run_dir, args.arm)
    transcript_path = run_dir / "transcript.ndjson"

    print(f"[r1/{task_name}/{args.arm}/{args.run_id}] running agent "
          f"(model={args.model}, timeout={args.timeout}s)...")
    try:
        agent_result = run_agent(workspace, prompt, args.model, args.timeout,
                                 transcript_path)
    except subprocess.TimeoutExpired:
        agent_result = {"exit_code": None, "stderr_tail": "TIMEOUT"}

    print(f"[r1/{task_name}/{args.arm}/{args.run_id}] verifying...")
    verification = run_verification(task_dir, workspace)

    metrics = analyze(transcript_path)
    record = {
        "experiment": "r1_ablation",
        "task": task_name,
        "arm": args.arm,
        "run_id": args.run_id,
        "agent_cli": "opencode",
        "model": args.model,
        "agents_md_chars": len(agents_md_for(args.arm)),
        "agent": agent_result,
        "verification": verification,
        "metrics": metrics,
    }
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    status = "PASS" if verification["passed"] else "FAIL"
    total = metrics["tokens"]["grand_total"]
    reads = metrics["behavior"]["distinct_files_read"]
    turns = metrics["behavior"]["main_turns"]
    print(f"[r1/{task_name}/{args.arm}/{args.run_id}] {status} | "
          f"tokens={total:,} | turns={turns} | reads={reads} | -> {metrics_path}")


if __name__ == "__main__":
    main()
