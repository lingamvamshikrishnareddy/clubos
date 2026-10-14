"""Fetch one StatsBomb open-data match and print per-player stats as JSON lines.

Usage: uv run clubos-ingest-statsbomb <match_id>
"""

from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import asdict

from .statsbomb import aggregate_match

EVENTS_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    match_id = sys.argv[1]
    with urllib.request.urlopen(EVENTS_URL.format(match_id=match_id), timeout=60) as response:
        events = json.load(response)
    for row in aggregate_match(match_id, events):
        print(json.dumps(asdict(row)))


if __name__ == "__main__":
    main()
