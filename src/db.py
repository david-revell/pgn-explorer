from __future__ import annotations

import sqlite3
from collections.abc import Iterable
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
    white_norm TEXT NOT NULL,
    black_norm TEXT NOT NULL,
    date_sort_key INTEGER NOT NULL,
    date_precision INTEGER NOT NULL,
    moves_san TEXT NOT NULL,
    pgn_text TEXT NOT NULL
);
"""


CREATE_POSITIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    ply INTEGER NOT NULL,
    position_key TEXT NOT NULL,
    next_move TEXT,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
"""


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_games_game_number ON games (game_number)",
    "CREATE INDEX IF NOT EXISTS idx_games_source_line ON games (source_line)",
    "CREATE INDEX IF NOT EXISTS idx_games_white ON games (white)",
    "CREATE INDEX IF NOT EXISTS idx_games_black ON games (black)",
    "CREATE INDEX IF NOT EXISTS idx_games_white_norm ON games (white_norm)",
    "CREATE INDEX IF NOT EXISTS idx_games_black_norm ON games (black_norm)",
    "CREATE INDEX IF NOT EXISTS idx_games_result ON games (result)",
    "CREATE INDEX IF NOT EXISTS idx_games_eco ON games (eco)",
    "CREATE INDEX IF NOT EXISTS idx_games_date ON games (date)",
    "CREATE INDEX IF NOT EXISTS idx_games_date_sort ON games (date_sort_key DESC, date_precision ASC, game_number DESC)",
    "CREATE INDEX IF NOT EXISTS idx_games_moves_san ON games (moves_san)",
    "CREATE INDEX IF NOT EXISTS idx_positions_position_key ON positions (position_key)",
    "CREATE INDEX IF NOT EXISTS idx_positions_game_ply ON positions (game_id, ply)",
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
    "white_norm",
    "black_norm",
    "date_sort_key",
    "date_precision",
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
    games_row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'games'
        """
    ).fetchone()
    positions_row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'positions'
        """
    ).fetchone()
    if games_row is None or positions_row is None:
        return False

    games_columns = {
        column_info["name"]
        for column_info in connection.execute("PRAGMA table_info(games)").fetchall()
    }
    positions_columns = {
        column_info["name"]
        for column_info in connection.execute("PRAGMA table_info(positions)").fetchall()
    }
    return REQUIRED_COLUMNS.issubset(games_columns) and {
        "id",
        "game_id",
        "ply",
        "position_key",
        "next_move",
    }.issubset(positions_columns)


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_TABLE_SQL)
    connection.execute(CREATE_POSITIONS_TABLE_SQL)
    if not database_has_required_schema(connection):
        connection.commit()
        return

    for statement in INDEX_STATEMENTS:
        connection.execute(statement)
    connection.commit()


def _insert_games_batch(
    connection: sqlite3.Connection,
    games: list[dict],
    positions_by_game_number: dict[int, list[dict[str, object]]],
) -> tuple[int, int]:
    if not games:
        return (0, 0)

    connection.executemany(
        """
        INSERT INTO games (
            game_number, source_line, source_file, event, site, date, round, white, black, result, eco,
            white_elo, black_elo, ply_count, event_date, termination, time_control,
            white_norm, black_norm, date_sort_key, date_precision, moves_san, pgn_text
        )
        VALUES (
            :game_number, :source_line, :source_file, :event, :site, :date, :round, :white, :black, :result, :eco,
            :white_elo, :black_elo, :ply_count, :event_date, :termination, :time_control,
            :white_norm, :black_norm, :date_sort_key, :date_precision, :moves_san, :pgn_text
        )
        """,
        games,
    )

    min_game_number = min(int(game["game_number"]) for game in games)
    max_game_number = max(int(game["game_number"]) for game in games)
    game_id_by_number = {
        int(row["game_number"]): int(row["id"])
        for row in connection.execute(
            """
            SELECT id, game_number
            FROM games
            WHERE game_number BETWEEN ? AND ?
            """,
            (min_game_number, max_game_number),
        ).fetchall()
    }

    position_rows: list[dict[str, object]] = []
    for game_number, game_positions in positions_by_game_number.items():
        game_id = game_id_by_number[game_number]
        for position in game_positions:
            position_rows.append(
                {
                    "game_id": game_id,
                    "ply": position["ply"],
                    "position_key": position["position_key"],
                    "next_move": position["next_move"],
                }
            )

    connection.executemany(
        """
        INSERT INTO positions (game_id, ply, position_key, next_move)
        VALUES (:game_id, :ply, :position_key, :next_move)
        """,
        position_rows,
    )
    return (len(games), len(position_rows))


def replace_games(
    connection: sqlite3.Connection,
    parsed_games: Iterable[tuple[dict, list[dict[str, object]]]],
    batch_size: int = 250,
) -> tuple[int, int]:
    connection.executescript(
        """
        DROP TABLE IF EXISTS positions;
        DROP TABLE IF EXISTS games;
        """
    )
    connection.commit()
    initialize_database(connection)

    total_games = 0
    total_positions = 0
    games_batch: list[dict] = []
    positions_by_game_number: dict[int, list[dict[str, object]]] = {}

    for game_row, position_rows in parsed_games:
        game_number = int(game_row["game_number"])
        games_batch.append(game_row)
        positions_by_game_number[game_number] = position_rows

        if len(games_batch) >= batch_size:
            inserted_games, inserted_positions = _insert_games_batch(
                connection,
                games_batch,
                positions_by_game_number,
            )
            total_games += inserted_games
            total_positions += inserted_positions
            games_batch = []
            positions_by_game_number = {}

    if games_batch:
        inserted_games, inserted_positions = _insert_games_batch(
            connection,
            games_batch,
            positions_by_game_number,
        )
        total_games += inserted_games
        total_positions += inserted_positions

    connection.commit()
    return (total_games, total_positions)
