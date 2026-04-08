from __future__ import annotations

import pandas as pd


PLAYER_ALIAS_GROUPS = {
    "Malcolm Pawlak": {
        "search_names": [
            "Malcolm Pawlak",
            "oldjingleballicks",
            "Oldjingleballiks",
        ],
        "lookup_terms": [
            "Malcolm Pawlak",
            "oldjingleballicks",
            "Oldjingleballiks",
        ],
    }
}


def _normalize(value: str) -> str:
    return value.strip().lower()


def resolve_player_aliases(player_text: str) -> dict[str, object]:
    cleaned = player_text.strip()
    if not cleaned:
        return {
            "expanded": False,
            "canonical_name": "",
            "search_names": [],
            "display_aliases": [],
        }

    normalized_input = _normalize(cleaned)
    for canonical_name, config in PLAYER_ALIAS_GROUPS.items():
        lookup_terms = {_normalize(term) for term in config["lookup_terms"]}
        if normalized_input in lookup_terms:
            return {
                "expanded": True,
                "canonical_name": canonical_name,
                "search_names": [_normalize(name) for name in config["search_names"]],
                "display_aliases": list(config["search_names"]),
            }

    return {
        "expanded": False,
        "canonical_name": "",
        "search_names": [],
        "display_aliases": [],
    }


def load_alias_table() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for canonical_name, config in PLAYER_ALIAS_GROUPS.items():
        rows.append(
            {
                "Canonical name": canonical_name,
                "Aliases": ", ".join(config["search_names"]),
            }
        )

    return pd.DataFrame(rows)
