from __future__ import annotations

import csv
from pathlib import Path


def load_opening_rows(tsv_path: Path | str) -> list[dict[str, str]]:
    path = Path(tsv_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [
            {
                "position_key": (row.get("position_key") or "").strip(),
                "eco": (row.get("eco") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "pgn": (row.get("pgn") or "").strip(),
                "uci": (row.get("uci") or "").strip(),
            }
            for row in reader
            if (row.get("position_key") or "").strip()
            and (row.get("eco") or "").strip()
            and (row.get("name") or "").strip()
        ]
