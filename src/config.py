from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    mode: str
    pgn_path: Path
    db_path: Path
    allow_pgn_writes: bool


def load_config() -> AppConfig:
    mode = os.getenv("PGN_EXPLORER_MODE", "private").strip().lower() or "private"
    default_pgn_path = Path("pgn/all.pgn")
    default_db_path = Path("data/games.db")
    if mode == "public":
        default_pgn_path = Path("pgn/public_anonymised.pgn")
        default_db_path = Path("data/public_games.db")

    pgn_path = Path(os.getenv("PGN_EXPLORER_PGN_PATH", str(default_pgn_path)))
    db_path = Path(os.getenv("PGN_EXPLORER_DB_PATH", str(default_db_path)))
    allow_pgn_writes = _env_flag("PGN_EXPLORER_ALLOW_PGN_WRITES", mode != "public")
    return AppConfig(
        mode=mode,
        pgn_path=pgn_path,
        db_path=db_path,
        allow_pgn_writes=allow_pgn_writes,
    )


APP_CONFIG = load_config()
