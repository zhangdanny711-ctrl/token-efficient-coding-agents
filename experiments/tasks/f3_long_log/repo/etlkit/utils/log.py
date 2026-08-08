"""Deterministic run logging.

etlkit run logs are diffed across re-runs and machines in CI, so the
log must be byte-identical for identical inputs. Instead of wall-clock
timestamps, every line carries a simulated elapsed-time tick that
advances by a fixed amount per event. The tick is cosmetic; only the
ordering and content of lines matter.
"""

import sys

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class RunLog:
    """Writes one formatted line per event and keeps per-level counts."""

    def __init__(self, stream=None, step_ms=2.6, verbose=True):
        self.stream = stream if stream is not None else sys.stdout
        self.step_ms = step_ms
        self.verbose = verbose
        self.elapsed_ms = 0.0
        self.counts = {level: 0 for level in LEVELS}

    def _emit(self, level, stage, message):
        self.elapsed_ms += self.step_ms
        self.counts[level] += 1
        line = "[%9.1fms] %-7s %-20s %s" % (self.elapsed_ms, level, stage, message)
        self.stream.write(line + "\n")

    def debug(self, stage, message):
        if self.verbose:
            self._emit("DEBUG", stage, message)

    def info(self, stage, message):
        self._emit("INFO", stage, message)

    def warning(self, stage, message):
        self._emit("WARNING", stage, message)

    def error(self, stage, message):
        self._emit("ERROR", stage, message)

    def banner(self, stage, title):
        self.info(stage, "=" * 12 + " " + title + " " + "=" * 12)

    def summary_counts(self):
        return dict(self.counts)
