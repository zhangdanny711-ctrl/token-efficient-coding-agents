"""Command-line entry point.

    python3 -m etlkit run <spec.json>     execute a job
    python3 -m etlkit check <spec.json>   validate the spec only
"""

import argparse
import sys

from .errors import SpecError
from .runner import run_job
from .spec import load_spec


def main(argv=None):
    parser = argparse.ArgumentParser(prog="etlkit")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="execute a job spec")
    run_p.add_argument("spec", help="path to the job spec JSON")

    check_p = sub.add_parser("check", help="validate a job spec without running it")
    check_p.add_argument("spec", help="path to the job spec JSON")

    args = parser.parse_args(argv)

    if args.command == "run":
        return run_job(args.spec)

    if args.command == "check":
        try:
            spec = load_spec(args.spec)
        except SpecError as exc:
            print("spec error: %s" % exc, file=sys.stderr)
            return 2
        print(
            "spec ok: job %r, %d checks, %d ops"
            % (spec["job"], len(spec["checks"]), len(spec["ops"]))
        )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
