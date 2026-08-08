"""Pipeline stages, executed in fixed order by the runner."""

from .extract import run_extract
from .validate import run_validate
from .transform import run_transform
from .load import run_load

STAGE_ORDER = ("extract", "validate", "transform", "load")

__all__ = ["run_extract", "run_validate", "run_transform", "run_load", "STAGE_ORDER"]
