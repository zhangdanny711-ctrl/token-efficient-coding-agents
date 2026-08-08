#!/usr/bin/env bash
# Run the validation set: every task under tasks/ (except smoke) x both conditions.
# Usage: bash run_batch.sh <run_id>
set -u
cd "$(dirname "$0")"
run_id="${1:-v1}"

for task in tasks/t1a_daterange tasks/t1b_slugify tasks/t2a_ledger tasks/t2b_eventbus tasks/t3a_pipeline; do
    for cond in baseline skill; do
        python3 run_experiment.py --task "$task" --condition "$cond" \
            --run-id "$run_id" --model claude-sonnet-5 --timeout 900
    done
done
echo "batch $run_id done"
