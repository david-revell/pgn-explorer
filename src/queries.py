from __future__ import annotations

import sqlite3

import pandas as pd


def load_games(
    connection: sqlite3.Connection,
    database_id: int | None = None,
    game_number: int | None = None,
    player: str = "",
    color: str = "Either",
    result: str = "Any",
    eco_prefix: str = "",
    limit: int = 200,
) -> pd.DataFrame:
    clauses: list[str] = []
    params: dict[str, object] = {"limit": limit}

    if database_id is not None:
        clauses.append("id = :database_id")
        params["database_id"] = database_id

    if game_number is not None:
        clauses.append("game_number = :game_number")
        params["game_number"] = game_number

    if player.strip():
        params["player"] = f"%{player.strip()}%"
        if color == "White":
            clauses.append("white LIKE :player")
        elif color == "Black":
            clauses.append("black LIKE :player")
        else:
            clauses.append("(white LIKE :player OR black LIKE :player)")

    if result != "Any":
        clauses.append("result = :result")
        params["result"] = result

    if eco_prefix.strip():
        clauses.append("eco LIKE :eco_prefix")
        params["eco_prefix"] = f"{eco_prefix.strip()}%"

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    query = f"""
        SELECT
            id, game_number, source_line, date, white, black, result, eco,
            white_elo, black_elo, event, site
        FROM games
        {where_sql}
        ORDER BY game_number DESC
        LIMIT :limit
    """
    return pd.read_sql_query(query, connection, params=params)


def load_game_by_id(connection: sqlite3.Connection, game_id: int) -> sqlite3.Row | None:
    cursor = connection.execute(
        """
        SELECT *
        FROM games
        WHERE id = ?
        """,
        (game_id,),
    )
    return cursor.fetchone()
