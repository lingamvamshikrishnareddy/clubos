"""StatsBomb open-data ingestion.

  clubos-ingest-statsbomb match <match_id>
      Print per-player stats for one match as JSON lines.

  clubos-ingest-statsbomb load <competition_id> <season_id>
      Load a competition-season into the database named by DATABASE_URL.
      IDs are listed in https://github.com/statsbomb/open-data/blob/master/data/competitions.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

import psycopg

from .load import fetch_json, load_competition_season
from .statsbomb import aggregate_match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    match = commands.add_parser("match")
    match.add_argument("match_id", type=int)
    load = commands.add_parser("load")
    load.add_argument("competition_id", type=int)
    load.add_argument("season_id", type=int)
    args = parser.parse_args()

    if args.command == "match":
        for row in aggregate_match(args.match_id, fetch_json(f"events/{args.match_id}.json")):
            print(json.dumps(asdict(row)))
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        run_id = load_competition_season(conn, args.competition_id, args.season_id)
        with conn.cursor() as cur:
            cur.execute("select status, records_ingested from ingestion_runs where id = %s", (run_id,))
            status, records = cur.fetchone()
    print(f"ingestion run {run_id}: {status}, {records} player-match rows")


if __name__ == "__main__":
    main()
