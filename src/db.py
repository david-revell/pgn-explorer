from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/games.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    event TEXT,
    site TEXT,
    date TEXT,
    round TEXT,
    white TEXT,
    black TEXT,
    result TEXT,
    eco TEXT,
    white_elo INTEGER,
    black_elo INTEGER,
    ply_count INTEGER,
    event_date TEXT,
    termination TEXT,
    time_control TEXT,
    moves_san TEXT NOT NULL,
    pgn_text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_white ON games (white);
CREATE INDEX IF NOT EXISTS idx_games_black ON games (black);
CREATE INDEX IF NOT EXISTS idx_games_result ON games (result);
CREATE INDEX IF NOT EXISTS idx_games_eco ON games (eco);
CREATE INDEX IF NOT EXISTS idx_games_date ON games (date);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()


def replace_games(connection: sqlite3.Connection, games: list[dict]) -> None:
    initialize_database(connection)
    connection.execute("DELETE FROM games")
    connection.executemany(
        """
        INSERT INTO games (
            source_file, event, site, date, round, white, black, result, eco,
            white_elo, black_elo, ply_count, event_date, termination, time_control,
            moves_san, pgn_text
        )
        VALUES (
            :source_file, :event, :site, :date, :round, :white, :black, :result, :eco,
            :white_elo, :black_elo, :ply_count, :event_date, :termination, :time_control,
            :moves_san, :pgn_text
        )
        """,
        games,
    )
    connection.commit()
