#!/usr/bin/env python3
"""Parse a Claude Code stream-json transcript into experiment metrics.

Usage:
    python3 analyze_trajectory.py <transcript.jsonl> [--json]

The transcript is the stdout of `claude -p --output-format stream-json --verbose`,
one JSON event per line. Main-context events have no `parent_tool_use_id`;
subagent events carry one, so their tokens are accounted separately (but still
included in totals — subagent cost must not be hidden).
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

SEARCH_BASH_RE = re.compile(r"\b(grep|rg|find|ag)\b")


def _classify_test_cmd(cmd):
    """Return 'narrow', 'full', or None for a Bash command string."""
    if "pytest" not in cmd:
        return None
    if "::" in cmd or " -k " in cmd:
        return "narrow"
    if re.search(r"\btest_\w+\.py\b", cmd):
        return "narrow"
    return "full"

LONG_OUTPUT_THRESHOLD_CHARS = 4000  # ~1k tokens; counts a tool_result as "long"

TOKEN_FIELDS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


def _iter_events(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate stray non-JSON lines


def _tool_result_text(block):
    """Flatten a tool_result content field (string or list of blocks) to text."""
    content = block.get("content", "")
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
    return "".join(parts)


def analyze(transcript_path):
    tokens_main = dict.fromkeys(TOKEN_FIELDS, 0)
    tokens_subagent = dict.fromkeys(TOKEN_FIELDS, 0)
    # usage is deduped by message id: the same assistant message can appear as
    # multiple stream events (text block, then tool_use block) carrying the
    # same cumulative usage object.
    usage_seen = {}  # message_id -> (is_subagent, usage)

    tool_counts = Counter()
    subagent_tool_counts = Counter()

    main_turn_ids = []  # ordered distinct main-context assistant message ids
    first_edit_msg_id = None

    reads_by_file = Counter()  # main-context Read counts per file_path
    repeated_reads = 0
    reads_with_limit = 0
    modified_files = set()

    long_outputs = 0
    result_event = None

    # Rule 1: was there any search (Grep/Glob, or grep/rg via Bash) before
    # the first Read of each file?
    search_seen = False
    reads_after_search = 0
    first_reads = 0

    # Rule 3 proxy: repeated identical actions / identical error outputs.
    action_signatures = Counter()  # (tool, canonical input) -> count
    repeated_actions = 0
    error_hashes = Counter()  # hash of failing tool_result text -> count
    pending_tool_errors = {}  # tool_use_id -> True (main context Bash/Edit)

    # Rule 4: ordering of narrow vs full test runs.
    test_sequence = []  # 'narrow' / 'full' in main-context order

    # Rule 5: assistant text volume.
    assistant_text_chars = 0

    for ev in _iter_events(transcript_path):
        ev_type = ev.get("type")
        is_subagent = bool(ev.get("parent_tool_use_id"))

        if ev_type == "result":
            result_event = ev
            continue

        if ev_type == "assistant":
            msg = ev.get("message", {})
            msg_id = msg.get("id")
            if msg_id:
                usage_seen[msg_id] = (is_subagent, msg.get("usage", {}) or {})
                if not is_subagent and msg_id not in main_turn_ids:
                    main_turn_ids.append(msg_id)

            for block in msg.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and not is_subagent:
                    assistant_text_chars += len(block.get("text", ""))
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                tool_input = block.get("input", {}) or {}
                if is_subagent:
                    subagent_tool_counts[name] += 1
                    continue
                tool_counts[name] += 1

                sig = (name, json.dumps(tool_input, sort_keys=True))
                action_signatures[sig] += 1
                if action_signatures[sig] > 1:
                    repeated_actions += 1

                if name in ("Grep", "Glob") or (
                    name == "Bash"
                    and SEARCH_BASH_RE.search(tool_input.get("command", ""))
                ):
                    search_seen = True

                if name == "Bash":
                    kind = _classify_test_cmd(tool_input.get("command", ""))
                    if kind:
                        test_sequence.append(kind)

                if name == "Read":
                    fp = tool_input.get("file_path", "")
                    if fp:
                        if reads_by_file[fp] > 0 and fp not in modified_files:
                            repeated_reads += 1
                        else:
                            first_reads += 1
                            if search_seen:
                                reads_after_search += 1
                        reads_by_file[fp] += 1
                        modified_files.discard(fp)
                    if "limit" in tool_input or "offset" in tool_input:
                        reads_with_limit += 1
                elif name in ("Edit", "Write", "NotebookEdit"):
                    fp = tool_input.get("file_path") or tool_input.get(
                        "notebook_path", ""
                    )
                    if fp:
                        modified_files.add(fp)
                    if name == "Edit" and first_edit_msg_id is None:
                        first_edit_msg_id = msg_id

        elif ev_type == "user" and not is_subagent:
            msg = ev.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        text = _tool_result_text(block)
                        if len(text) > LONG_OUTPUT_THRESHOLD_CHARS:
                            long_outputs += 1
                        if block.get("is_error") or "FAILED" in text or (
                            "Error" in text and "Traceback" in text
                        ):
                            error_hashes[
                                hashlib.md5(text.strip().encode()).hexdigest()
                            ] += 1

    for is_subagent, usage in usage_seen.values():
        bucket = tokens_subagent if is_subagent else tokens_main
        for field in TOKEN_FIELDS:
            bucket[field] += usage.get(field, 0) or 0

    turns_before_first_edit = None
    if first_edit_msg_id in main_turn_ids:
        turns_before_first_edit = main_turn_ids.index(first_edit_msg_id)

    # Authoritative totals come from the final `result` event: per-message
    # usage in stream events matches it exactly for input/cache fields but
    # output_tokens there is a streaming snapshot and undercounts.
    tokens_total = {
        f: tokens_main[f] + tokens_subagent[f] for f in TOKEN_FIELDS
    }
    result_usage = (result_event or {}).get("usage") or {}
    if result_usage:
        tokens_total = {f: result_usage.get(f, 0) or 0 for f in TOKEN_FIELDS}

    metrics = {
        "tokens": {
            "main": tokens_main,
            "subagent": tokens_subagent,
            "total": tokens_total,
            "total_source": "result_event" if result_usage else "event_sum",
            "grand_total": sum(tokens_total.values()),
        },
        "tool_calls": {
            "total": sum(tool_counts.values()),
            "by_tool": dict(tool_counts),
            "Read": tool_counts.get("Read", 0),
            "Edit": tool_counts.get("Edit", 0),
            "Write": tool_counts.get("Write", 0),
            "Bash": tool_counts.get("Bash", 0),
            "Task": tool_counts.get("Task", 0) + tool_counts.get("Explore", 0),
            "subagent_total": sum(subagent_tool_counts.values()),
            "subagent_by_tool": dict(subagent_tool_counts),
        },
        "behavior": {
            # Rule 1
            "search_before_read_rate": (
                round(reads_after_search / first_reads, 3) if first_reads else None
            ),
            "repeated_reads": repeated_reads,
            "distinct_files_read": len(reads_by_file),
            "reads_with_offset_or_limit": reads_with_limit,
            "long_outputs": long_outputs,
            "long_output_threshold_chars": LONG_OUTPUT_THRESHOLD_CHARS,
            # Rule 2 (subagent usage is in tool_calls.Task / tokens.subagent)
            # Rule 3 proxies
            "repeated_identical_actions": repeated_actions,
            "max_identical_error_repeats": (
                max(error_hashes.values()) if error_hashes else 0
            ),
            # Rule 4
            "turns_before_first_edit": turns_before_first_edit,
            "test_sequence": test_sequence,
            "narrow_test_before_full": (
                test_sequence.index("narrow") < test_sequence.index("full")
                if "narrow" in test_sequence and "full" in test_sequence
                else ("narrow" in test_sequence if test_sequence else None)
            ),
            # Rule 5
            "assistant_text_chars": assistant_text_chars,
            "main_turns": len(main_turn_ids),
        },
    }

    if result_event is not None:
        metrics["result"] = {
            "num_turns": result_event.get("num_turns"),
            "duration_ms": result_event.get("duration_ms"),
            "total_cost_usd": result_event.get("total_cost_usd"),
            "is_error": result_event.get("is_error"),
        }

    return metrics


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("transcript", type=Path)
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    args = ap.parse_args()

    metrics = analyze(args.transcript)
    if args.json:
        json.dump(metrics, sys.stdout, indent=2)
        print()
        return

    t = metrics["tokens"]
    print(f"== {args.transcript} ==")
    print(
        "tokens (main+subagent): "
        + ", ".join(f"{f}={t['total'][f]:,}" for f in TOKEN_FIELDS)
    )
    if any(t["subagent"].values()):
        print("  of which subagent: " + ", ".join(
            f"{f}={t['subagent'][f]:,}" for f in TOKEN_FIELDS))
    tc = metrics["tool_calls"]
    print(
        f"tool calls: total={tc['total']} "
        f"(Read={tc['Read']} Edit={tc['Edit']} Write={tc['Write']} "
        f"Bash={tc['Bash']} Task={tc['Task']})"
    )
    b = metrics["behavior"]
    print(
        f"behavior: repeated_reads={b['repeated_reads']}, "
        f"turns_before_first_edit={b['turns_before_first_edit']}, "
        f"long_outputs={b['long_outputs']}, main_turns={b['main_turns']}"
    )
    if "result" in metrics:
        r = metrics["result"]
        print(
            f"result: turns={r['num_turns']}, cost=${r['total_cost_usd']}, "
            f"duration={r['duration_ms']}ms, is_error={r['is_error']}"
        )


if __name__ == "__main__":
    main()
