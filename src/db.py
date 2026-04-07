from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/games.db")


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_number INTEGER NOT NULL,
    source_line INTEGER NOT NULL,
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
"""


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_games_game_number ON games (game_number)",
    "CREATE INDEX IF NOT EXISTS idx_games_source_line ON games (source_line)",
    "CREATE INDEX IF NOT EXISTS idx_games_white ON games (white)",
    "CREATE INDEX IF NOT EXISTS idx_games_black ON games (black)",
    "CREATE INDEX IF NOT EXISTS idx_games_result ON games (result)",
    "CREATE INDEX IF NOT EXISTS idx_games_eco ON games (eco)",
    "CREATE INDEX IF NOT EXISTS idx_games_date ON games (date)",
]


REQUIRED_COLUMNS = {
    "id",
    "game_number",
    "source_line",
    "source_file",
    "event",
    "site",
    "date",
    "round",
    "white",
    "black",
    "result",
    "eco",
    "white_elo",
    "black_elo",
    "ply_count",
    "event_date",
    "termination",
    "time_control",
    "moves_san",
    "pgn_text",
}


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def database_has_required_schema(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'games'
        """
    ).fetchone()
    if row is None:
        return False

    columns = {
        column_info["name"]
        for column_info in connection.execute("PRAGMA table_info(games)").fetchall()
    }
    return REQUIRED_COLUMNS.issubset(columns)


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_TABLE_SQL)
    if not database_has_required_schema(connection):
        connection.commit()
        return

    for statement in INDEX_STATEMENTS:
        connection.execute(statement)
    connection.commit()


def replace_games(connection: sqlite3.Connection, games: list[dict]) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS games;
        """
    )
    connection.commit()
    initialize_database(connection)
    connection.executemany(
        """
        INSERT INTO games (
            game_number, source_line, source_file, event, site, date, round, white, black, result, eco,
            white_elo, black_elo, ply_count, event_date, termination, time_control,
            moves_san, pgn_text
        )
        VALUES (
            :game_number, :source_line, :source_file, :event, :site, :date, :round, :white, :black, :result, :eco,
            :white_elo, :black_elo, :ply_count, :event_date, :termination, :time_control,
            :moves_san, :pgn_text
        )
        """,
        games,
    )
    connection.commit()
