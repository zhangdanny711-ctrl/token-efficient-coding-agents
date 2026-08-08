#!/usr/bin/env python3
"""Reproduce the release's headline statistics from archived metrics.

This script uses only the Python standard library. It audits the released run
count, rebuilds the OpenCode + GLM-5.2 20-vs-20 main comparison, and rebuilds
the six-task ecological-validity result. Reported p-values are Monte Carlo
permutation estimates, so the final digits can vary with the seed and number
of permutations.

Usage:
    python3 experiments/reproduce_key_results.py
    python3 experiments/reproduce_key_results.py --permutations 1000000
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
ARCHIVE_DIRS = (
    "runs",
    "runs_batching_ablation",
    "runs_f5f7",
    "runs_r1_ablation",
    "runs_eco_validity",
    "runs_difficulty_band",
)
MAIN_TASKS = {"f1_deep_chain", "f3_long_log"}


def read_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_paths(directory: Path) -> list[Path]:
    return sorted(directory.rglob("metrics.json"))


def is_contaminated(path: Path) -> bool:
    return (path.parent / "CONTAMINATED.md").exists()


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def percent_delta(baseline: float, treatment: float) -> float:
    return 100.0 * (treatment / baseline - 1.0)


def get_metric(record: dict, *keys: str) -> float:
    value = record
    for key in keys:
        value = value[key]
    return value


def audit_release() -> tuple[int, int, int, int]:
    paths = [
        path
        for dirname in ARCHIVE_DIRS
        for path in metric_paths(EXPERIMENTS_DIR / dirname)
    ]
    excluded = [path for path in paths if is_contaminated(path)]
    valid = [path for path in paths if not is_contaminated(path)]
    passed = sum(bool(read_record(path)["verification"]["passed"]) for path in valid)

    expected = (230, 4, 226, 226)
    observed = (len(paths), len(excluded), len(valid), passed)
    if observed != expected:
        raise RuntimeError(
            "release audit no longer matches the frozen dataset: "
            f"expected total/excluded/valid/passed={expected}, observed={observed}"
        )
    return observed


def main_study_records() -> tuple[list[dict], list[dict]]:
    baseline: list[dict] = []
    skill: list[dict] = []

    for path in metric_paths(EXPERIMENTS_DIR / "runs"):
        if is_contaminated(path):
            continue
        record = read_record(path)
        if (
            record.get("agent_cli") != "opencode"
            or record.get("task") not in MAIN_TASKS
        ):
            continue
        if record.get("condition") == "baseline":
            baseline.append(record)
        elif record.get("condition") == "skill":
            skill.append(record)

    # The preregistered main pool reuses the 12 protocol-identical control
    # runs from the batching ablation as additional baseline observations.
    for path in metric_paths(EXPERIMENTS_DIR / "runs_batching_ablation"):
        record = read_record(path)
        if record.get("arm") == "control" and "smoke" not in path.parent.name:
            baseline.append(record)

    if (len(baseline), len(skill)) != (20, 20):
        raise RuntimeError(
            f"expected main-study n=(20, 20), got {(len(baseline), len(skill))}"
        )
    return baseline, skill


def one_sided_permutation_p(
    baseline: Sequence[float],
    treatment: Sequence[float],
    permutations: int,
    seed: int,
) -> float:
    """Monte Carlo p-value for treatment mean < baseline mean."""
    pooled = list(baseline) + list(treatment)
    baseline_n = len(baseline)
    treatment_n = len(treatment)
    total = sum(pooled)
    observed = mean(treatment) - mean(baseline)
    rng = random.Random(seed)
    hits = 0

    for _ in range(permutations):
        treatment_sum = sum(
            pooled[index]
            for index in rng.sample(range(len(pooled)), treatment_n)
        )
        baseline_sum = total - treatment_sum
        permuted = treatment_sum / treatment_n - baseline_sum / baseline_n
        if permuted <= observed:
            hits += 1
    return (hits + 1) / (permutations + 1)


def ecological_records() -> dict[str, dict[str, list[dict]]]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: {"baseline": [], "skill": []}
    )
    for path in metric_paths(EXPERIMENTS_DIR / "runs_eco_validity"):
        record = read_record(path)
        grouped[record["task"]][record["condition"]].append(record)

    if len(grouped) != 6:
        raise RuntimeError(f"expected six ecological tasks, got {len(grouped)}")
    for task, arms in grouped.items():
        shape = (len(arms["baseline"]), len(arms["skill"]))
        if shape != (4, 4):
            raise RuntimeError(f"expected {task} n=(4, 4), got {shape}")
    return dict(grouped)


def stratified_median_delta(
    grouped: dict[str, dict[str, list[dict]]]
) -> tuple[float, list[tuple[str, float, float, float]]]:
    rows = []
    for task, arms in sorted(grouped.items()):
        baseline = [
            get_metric(record, "metrics", "tokens", "grand_total")
            for record in arms["baseline"]
        ]
        skill = [
            get_metric(record, "metrics", "tokens", "grand_total")
            for record in arms["skill"]
        ]
        baseline_median = statistics.median(baseline)
        skill_median = statistics.median(skill)
        delta = skill_median / baseline_median - 1.0
        rows.append((task, baseline_median, skill_median, delta))
    return mean([row[3] for row in rows]), rows


def stratified_permutation_p(
    grouped: dict[str, dict[str, list[dict]]],
    observed: float,
    permutations: int,
    seed: int,
) -> float:
    """Shuffle four-vs-four labels within each task, then average deltas."""
    null_deltas: list[list[float]] = []
    for _, arms in sorted(grouped.items()):
        values = [
            get_metric(record, "metrics", "tokens", "grand_total")
            for condition in ("baseline", "skill")
            for record in arms[condition]
        ]
        task_null = []
        all_indices = set(range(len(values)))
        for skill_indices_tuple in itertools.combinations(range(len(values)), 4):
            skill_indices = set(skill_indices_tuple)
            baseline_indices = all_indices - skill_indices
            skill_median = statistics.median(values[index] for index in skill_indices)
            baseline_median = statistics.median(
                values[index] for index in baseline_indices
            )
            task_null.append(skill_median / baseline_median - 1.0)
        null_deltas.append(task_null)

    rng = random.Random(seed)
    hits = 0
    for _ in range(permutations):
        statistic = mean([rng.choice(task_null) for task_null in null_deltas])
        if statistic <= observed:
            hits += 1
    return (hits + 1) / (permutations + 1)


def values(records: Iterable[dict], *keys: str) -> list[float]:
    return [get_metric(record, *keys) for record in records]


def verify_headline_values(
    baseline_tokens: Sequence[float],
    skill_tokens: Sequence[float],
    ecological_delta: float,
) -> None:
    checks = (
        math.isclose(mean(baseline_tokens), 184245.05, abs_tol=0.01),
        math.isclose(mean(skill_tokens), 149091.75, abs_tol=0.01),
        math.isclose(ecological_delta, -0.3613037254, abs_tol=1e-10),
    )
    if not all(checks):
        raise RuntimeError("headline values no longer match the frozen release")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--permutations",
        type=int,
        default=100_000,
        help="Monte Carlo permutations per test (default: 100000)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.permutations < 1:
        parser.error("--permutations must be positive")

    total, excluded, valid, passed = audit_release()
    baseline, skill = main_study_records()
    baseline_tokens = values(baseline, "metrics", "tokens", "grand_total")
    skill_tokens = values(skill, "metrics", "tokens", "grand_total")
    baseline_reads = values(
        baseline, "metrics", "behavior", "distinct_files_read"
    )
    skill_reads = values(skill, "metrics", "behavior", "distinct_files_read")
    main_p = one_sided_permutation_p(
        baseline_tokens,
        skill_tokens,
        permutations=args.permutations,
        seed=args.seed,
    )

    ecological = ecological_records()
    ecological_delta, ecological_rows = stratified_median_delta(ecological)
    ecological_p = stratified_permutation_p(
        ecological,
        observed=ecological_delta,
        permutations=args.permutations,
        seed=args.seed,
    )
    verify_headline_values(baseline_tokens, skill_tokens, ecological_delta)

    print("Release audit")
    print(f"  metrics files: {total}")
    print(f"  excluded contaminated runs: {excluded}")
    print(f"  valid runs passing verification: {passed}/{valid}")
    print()
    print("Main study: OpenCode + GLM-5.2 (20 baseline vs 20 skill)")
    print(f"  mean tokens: {mean(baseline_tokens):,.0f} -> {mean(skill_tokens):,.0f}")
    print(
        "  mean token delta: "
        f"{percent_delta(mean(baseline_tokens), mean(skill_tokens)):.1f}%"
    )
    print(
        "  median token delta: "
        f"{percent_delta(statistics.median(baseline_tokens), statistics.median(skill_tokens)):.1f}%"
    )
    print(f"  mean distinct files read: {mean(baseline_reads):.1f} -> {mean(skill_reads):.1f}")
    print(f"  one-sided permutation p: {main_p:.4f}")
    print()
    print("Ecological validity: six historical OSS bugs (4 vs 4 per task)")
    for task, baseline_median, skill_median, delta in ecological_rows:
        print(
            f"  {task}: {baseline_median:,.0f} -> {skill_median:,.0f} "
            f"({delta * 100:.1f}%)"
        )
    print(f"  task-stratified median delta: {ecological_delta * 100:.1f}%")
    print(f"  stratified permutation p: {ecological_p:.4f}")
    print()
    print(
        f"Reproduction checks: PASS (seed={args.seed}, "
        f"permutations={args.permutations:,})"
    )


if __name__ == "__main__":
    main()
