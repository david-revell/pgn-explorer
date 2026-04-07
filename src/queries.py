from __future__ import annotations

import sqlite3

import pandas as pd


def load_games(
    connection: sqlite3.Connection,
    player: str = "",
    color: str = "Either",
    result: str = "Any",
    eco_prefix: str = "",
    limit: int = 200,
) -> pd.DataFrame:
    clauses: list[str] = []
    params: dict[str, object] = {"limit": limit}

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
            id, date, white, black, result, eco, white_elo, black_elo, event, site
        FROM games
        {where_sql}
        ORDER BY date DESC, id DESC
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
