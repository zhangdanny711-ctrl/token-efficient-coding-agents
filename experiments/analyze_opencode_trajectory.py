#!/usr/bin/env python3
"""Parse an OpenCode `run --format json` NDJSON transcript into experiment metrics.

Usage:
    python3 analyze_opencode_trajectory.py <transcript.ndjson> [--json]

Emits the same metrics schema as analyze_trajectory.py (Claude Code) so
metrics.json / summarize_runs.py / report tables work unchanged.

Schema mapping (OpenCode -> Claude Code):
    step_finish part.tokens.input        -> input_tokens
    step_finish part.tokens.output
      + part.tokens.reasoning            -> output_tokens
    step_finish part.tokens.cache.read   -> cache_read_input_tokens
    step_finish part.tokens.cache.write  -> cache_creation_input_tokens
    tool part (tool/callID/state)        -> tool_use + tool_result
    part.messageID                       -> assistant message id (turn)

Totals are the sum over step_finish events; verified identical to the
session-level totals reported by `opencode export`.

Caveats:
  - OpenCode tool names are lowercase (`read`, `edit`, ...) and the Read
    input key is `filePath`; both are normalized to Claude Code names here.
  - Subagent attribution: no `parent_tool_use_id` analogue has been observed
    in the OpenCode stream; `tokens.subagent` / `subagent_by_tool` stay zero
    and any `task` tool call is counted under Task in the main context.
  - `reasoning` tokens are folded into output_tokens (Claude Code bills
    thinking as output); the raw value is preserved in tokens.reasoning_raw.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_trajectory import (  # noqa: E402
    LONG_OUTPUT_THRESHOLD_CHARS,
    SEARCH_BASH_RE,
    TOKEN_FIELDS,
    _classify_test_cmd,
)

# OpenCode tool name -> Claude Code tool name used in our metrics.
TOOL_NAME_MAP = {
    "read": "Read",
    "edit": "Edit",
    "write": "Write",
    "bash": "Bash",
    "glob": "Glob",
    "grep": "Grep",
    "list": "List",
    "ls": "List",
    "task": "Task",
    "todowrite": "TodoWrite",
    "todoread": "TodoRead",
    "webfetch": "WebFetch",
    "patch": "Patch",
}


def _norm_tool(name):
    return TOOL_NAME_MAP.get(name, name.capitalize() if name else "?")


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


def analyze(transcript_path):
    tokens_main = dict.fromkeys(TOKEN_FIELDS, 0)
    tokens_subagent = dict.fromkeys(TOKEN_FIELDS, 0)  # stays zero, see module doc
    reasoning_raw = 0
    total_cost = 0.0

    tool_counts = Counter()
    subagent_tool_counts = Counter()

    main_turn_ids = []  # ordered distinct assistant messageIDs
    first_edit_msg_id = None

    reads_by_file = Counter()
    repeated_reads = 0
    reads_with_limit = 0
    modified_files = set()

    long_outputs = 0

    search_seen = False
    reads_after_search = 0
    first_reads = 0

    action_signatures = Counter()
    repeated_actions = 0
    error_hashes = Counter()

    test_sequence = []
    assistant_text_chars = 0
    text_chars_by_part = {}  # part id -> chars (text parts can restream as they grow)

    first_ts = None
    last_ts = None
    is_error = False
    session_id = None

    # The stream can emit a tool part more than once as its state advances
    # (pending -> running -> completed); keep first-seen order, last state.
    tool_order = []  # callID order of first appearance
    tool_last = {}  # callID -> (tool_name, state, messageID)

    for ev in _iter_events(transcript_path):
        ev_type = ev.get("type")
        ts = ev.get("timestamp")
        if isinstance(ts, (int, float)):
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        session_id = ev.get("sessionID") or session_id

        part = ev.get("part") or {}
        part_type = part.get("type")
        msg_id = part.get("messageID")
        if msg_id and msg_id not in main_turn_ids:
            main_turn_ids.append(msg_id)

        if "error" in (ev_type or ""):
            is_error = True

        if part_type == "text":
            pid = part.get("id")
            text_chars_by_part[pid] = len(part.get("text", ""))
        elif part_type == "tool":
            call_id = part.get("callID") or part.get("id")
            if call_id not in tool_last:
                tool_order.append(call_id)
            tool_last[call_id] = (part.get("tool", "?"), part.get("state") or {}, msg_id)
        elif part_type == "step-finish":
            tk = part.get("tokens") or {}
            cache = tk.get("cache") or {}
            tokens_main["input_tokens"] += tk.get("input", 0) or 0
            tokens_main["output_tokens"] += (tk.get("output", 0) or 0) + (
                tk.get("reasoning", 0) or 0
            )
            reasoning_raw += tk.get("reasoning", 0) or 0
            tokens_main["cache_read_input_tokens"] += cache.get("read", 0) or 0
            tokens_main["cache_creation_input_tokens"] += cache.get("write", 0) or 0
            total_cost += part.get("cost", 0) or 0
            if part.get("reason") == "error":
                is_error = True

    assistant_text_chars = sum(text_chars_by_part.values())

    # Second pass over tools in first-appearance order, using final state.
    for call_id in tool_order:
        raw_name, state, msg_id = tool_last[call_id]
        name = _norm_tool(raw_name)
        tool_input = state.get("input") or {}
        output = state.get("output") or ""
        if not isinstance(output, str):
            output = json.dumps(output)

        tool_counts[name] += 1

        sig = (name, json.dumps(tool_input, sort_keys=True))
        action_signatures[sig] += 1
        if action_signatures[sig] > 1:
            repeated_actions += 1

        if name in ("Grep", "Glob") or (
            name == "Bash" and SEARCH_BASH_RE.search(tool_input.get("command", ""))
        ):
            search_seen = True

        if name == "Bash":
            kind = _classify_test_cmd(tool_input.get("command", ""))
            if kind:
                test_sequence.append(kind)

        if name == "Read":
            fp = tool_input.get("filePath") or tool_input.get("file_path", "")
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
        elif name in ("Edit", "Write", "Patch"):
            fp = tool_input.get("filePath") or tool_input.get("file_path", "")
            if fp:
                modified_files.add(fp)
            if name == "Edit" and first_edit_msg_id is None:
                first_edit_msg_id = msg_id

        if len(output) > LONG_OUTPUT_THRESHOLD_CHARS:
            long_outputs += 1
        if state.get("status") == "error" or "FAILED" in output or (
            "Error" in output and "Traceback" in output
        ):
            error_hashes[hashlib.md5(output.strip().encode()).hexdigest()] += 1

    turns_before_first_edit = None
    if first_edit_msg_id in main_turn_ids:
        turns_before_first_edit = main_turn_ids.index(first_edit_msg_id)

    tokens_total = dict(tokens_main)  # no subagent bucket, see module doc

    metrics = {
        "tokens": {
            "main": tokens_main,
            "subagent": tokens_subagent,
            "total": tokens_total,
            "total_source": "step_finish_sum",
            "grand_total": sum(tokens_total.values()),
            "reasoning_raw": reasoning_raw,
        },
        "tool_calls": {
            "total": sum(tool_counts.values()),
            "by_tool": dict(tool_counts),
            "Read": tool_counts.get("Read", 0),
            "Edit": tool_counts.get("Edit", 0),
            "Write": tool_counts.get("Write", 0),
            "Bash": tool_counts.get("Bash", 0),
            "Task": tool_counts.get("Task", 0),
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
        "result": {
            "num_turns": len(main_turn_ids),
            "duration_ms": (
                int(last_ts - first_ts)
                if first_ts is not None and last_ts is not None
                else None
            ),
            "total_cost_usd": round(total_cost, 6),
            "is_error": is_error,
        },
        "opencode": {
            "session_id": session_id,
        },
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
        "tokens: " + ", ".join(f"{f}={t['total'][f]:,}" for f in TOKEN_FIELDS)
    )
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
    r = metrics["result"]
    print(
        f"result: turns={r['num_turns']}, cost=${r['total_cost_usd']}, "
        f"duration={r['duration_ms']}ms, is_error={r['is_error']}"
    )


if __name__ == "__main__":
    main()
