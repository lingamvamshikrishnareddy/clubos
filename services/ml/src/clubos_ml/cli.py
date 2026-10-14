"""clubos-ml run [--as-of YYYY-MM-DD]

Computes valuations, forecasts, tactical-fit recommendations and workload indicators
for every sport in the database named by DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import psycopg

from .pipeline import run_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--as-of", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        summary = run_all(conn, args.as_of)
    for name, count in summary.items():
        print(f"{name:<20} {count:>7,}")


if __name__ == "__main__":
    main()
