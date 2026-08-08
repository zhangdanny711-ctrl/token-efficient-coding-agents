---
name: token-efficient-coding
description: Use when working on coding tasks (bug fixes, features, refactoring) to complete them with less context waste — minimal reads, delegated exploration, progress-aware iteration, adaptive planning, and concise output. Quality comes first; these rules cut cost, not correctness.
---

# Token-Efficient Coding

Complete the task correctly with the least context you need. Every observation you pull in
(file contents, logs, test output) stays in history and is re-sent on every later turn, so
acquire it deliberately. Never trade task correctness for token savings: when a rule below
conflicts with getting the job done right, do the job right.

## Workflow

1. Understand the goal and acceptance criteria before touching code.
2. Locate: search for relevant symbols/files before reading anything.
3. Read the minimum code that supports your current hypothesis.
4. Edit locally and run the cheapest relevant verification.
5. On failure, act on the new evidence; if no new evidence, change approach (Rule 3).
6. Finish with the verification the task actually requires, then report conclusions.

## Rule 1 — Minimal context acquisition

**Behavior:** Search before you read: use Grep/Glob to find where the relevant code lives,
then Read only the region you need (use offset/limit for large files). Do not re-read a file
you have already read unless you or something else changed it — rely on what is already in
context. When running commands that can produce long output (test suites, builds, servers),
constrain the output: run the narrow command, or filter with `tail`/`grep` to the failing part.

**Applies when:** any file access or command execution during investigation and fixing.

**Exceptions:** Small files (under ~100 lines) are fine to read whole. If a targeted read
leaves you unsure about surrounding behavior — imports, class contracts, security-sensitive
logic — widen the read; missing context that causes a wrong fix costs far more than the read.

## Rule 2 — Delegate exploration

**Behavior:** When answering a question would require skimming roughly three or more files
(how is X structured, where do all callers of Y live, which module owns Z), delegate it to an
Explore/Task subagent and consume only its summary, instead of reading those files yourself.
Ask the subagent a specific question so it returns a conclusion, not file dumps.

**Applies when:** open-ended codebase exploration, especially early in an unfamiliar task.

**Exceptions:** If you already know the one or two files that answer the question, just read
them — delegation has overhead and only pays off when the search space is genuinely wide.
Code you are about to edit should be read directly by you, not summarized secondhand.

## Rule 3 — Track progress; stop unproductive paths

**Behavior:** After each fix-verify iteration, ask: did this round produce new evidence — a
different error, a newly passing test, a hypothesis confirmed or eliminated, a narrower
suspect region? If two consecutive rounds produce no new evidence (same error, same failing
tests, near-identical edits around the same guess), stop that path. Re-locate from scratch
with fresh search terms, simplify to a smaller reproduction, or ask the user the specific
question that would unblock you. Do not retry variations of the same unverified idea.

**Applies when:** any debugging or fix-verify loop, especially after the first failed attempt.

**Exceptions:** A failure that eliminates a hypothesis IS progress — continue. If you have a
concrete reason the next attempt differs materially from the last, one more try is reasonable;
say what the new reason is before trying.

## Rule 4 — Match effort to the task

**Behavior:** For a task with a clear, localized cause, go straight to locate → fix → verify;
do not write a long upfront plan. Verify with the cheapest relevant check first — the single
test or reproduction that covers your change — and only widen to the fuller test suite once it
passes, or at the end if the task calls for regression safety. Escalate to explicit planning
only when the first direct attempt fails, or when the change turns out to span modules, touch
public APIs, or carry migration/compatibility risk.

**Applies when:** deciding how much planning and how much verification each stage needs.

**Exceptions:** If the task is evidently high-risk from the start (cross-cutting change, data
migration, security-sensitive), plan first — that planning is buying quality, not wasting it.
Never skip verification entirely to save cost; cheap-first does not mean none.

## Rule 5 — Output discipline

**Behavior:** Modify files with targeted Edits rather than rewriting whole files; keep each
edit scoped to the lines that change. In your messages, do not restate code you did not
change, do not paste file contents back to the user, and keep progress narration brief.
Final reports state the conclusion, what changed, and the verification evidence — not a
replay of the process.

**Applies when:** every file modification and every message you write.

**Exceptions:** Creating a genuinely new file requires Write — that is fine. Quote code when
the user asks to see it, or when a short snippet is the clearest way to explain a decision.
