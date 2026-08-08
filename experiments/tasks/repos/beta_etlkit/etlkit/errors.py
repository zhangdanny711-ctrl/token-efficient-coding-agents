"""Error hierarchy for etlkit.

Two broad families:

* Fatal errors (SpecError, ExtractError, LoadError) abort the run —
  they mean the job itself is unusable, not that a row was bad.
* RecordError marks a single-record failure. Stages catch it (and any
  other per-record exception), route the record to the reject pile,
  and keep going; the run then finishes DEGRADED instead of crashing.
"""


class EtlError(Exception):
    """Base class for all etlkit errors."""


class SpecError(EtlError):
    """The job spec file is missing, malformed, or self-contradictory."""


class ExtractError(EtlError):
    """A source file could not be opened or parsed at all."""


class LoadError(EtlError):
    """An output target could not be written."""


class RecordError(EtlError):
    """A single record failed a stage.

    Carries enough context to produce a useful reject entry without
    the stage having to re-derive it.
    """

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


class CheckFailure(RecordError):
    """A validation rule rejected a record."""
