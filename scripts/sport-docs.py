#!/usr/bin/env python3
"""Generates docs/sports/reference/<sport>.md from packages/sports/<sport>/sport.json.

    python3 scripts/sport-docs.py          # write the files
    python3 scripts/sport-docs.py --check  # exit 1 if they are out of date (used in CI)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "sports" / "reference"


def render(sport: dict) -> str:
    lines = [f"# {sport['name']} reference", "",
             f"Generated from `packages/sports/{sport['id'].replace('_', '-')}/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.", ""]
    exp = sport["exposure"]
    lines += ["## Exposure", "",
              f"- Default: **{exp['label']}**, values shown per {exp['per']}; low-sample below {exp['minimumForComparison']}."]
    for role, unit in (sport.get("roleExposure") or {}).items():
        lines.append(f"- `{role}`: **{unit['label']}**, per {unit['per']}; low-sample below {unit['minimumForComparison']}.")
    lines += ["", f"Valuation basis: **{sport['valuationBasis'].replace('_', ' ')}**.", "", "## Roles and comparison metrics", "",
              "| Role | Group | Compared on |", "|---|---|---|"]
    for role in sport["roles"]:
        metrics = ", ".join(f"`{k}`" for k in sport["comparisonMetrics"][role["key"]])
        lines.append(f"| {role['label']} (`{role['key']}`) | {role['group']} | {metrics} |")
    lines += ["", "## Metrics", "", "| Key | Metric | Normalisation | Better | Typical | Description |", "|---|---|---|---|---|---|"]
    for m in sport["metrics"]:
        typical = "–".join(str(v) for v in m.get("typical", [])) or ""
        better = "higher" if m["higherIsBetter"] else "lower"
        lines.append(f"| `{m['key']}` | {m['label']} | {m['normalisation'].replace('_', ' ')} | {better} | {typical} | {m['description']} |")
    lines += ["", "## Event types", "", ", ".join(f"`{e['key']}`" for e in sport["eventTypes"]), "", "## Video tags", ""]
    for group in sport["videoTags"]:
        lines.append(f"- **{group['label']}** (`{group['key']}`): {', '.join(group['values'])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "packages" / "sports").glob("*/sport.json")):
        sport = json.loads(path.read_text())
        target = OUT / f"{path.parent.name}.md"
        content = render(sport)
        if check:
            if not target.exists() or target.read_text() != content:
                stale.append(str(target.relative_to(ROOT)))
        else:
            target.write_text(content)
    if stale:
        print("Out of date (run python3 scripts/sport-docs.py):", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
