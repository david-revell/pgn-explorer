from __future__ import annotations

import sqlite3

import pandas as pd


def normalize_aliases(raw_aliases: str) -> list[str]:
    aliases = [alias.strip().lower() for alias in raw_aliases.split(",")]
    return [alias for alias in aliases if alias]


def _build_alias_match_clause(
    field_name: str,
    aliases: list[str],
    params: dict[str, object],
    prefix: str,
) -> str:
    if not aliases:
        return "0"

    placeholders: list[str] = []
    for index, alias in enumerate(aliases):
        key = f"{prefix}_{index}"
        params[key] = alias
        placeholders.append(f":{key}")

    alias_sql = ", ".join(placeholders)
    return f"LOWER(TRIM(COALESCE({field_name}, ''))) IN ({alias_sql})"


def _append_not_my_game_clause(
    clauses: list[str],
    params: dict[str, object],
    aliases: list[str],
) -> None:
    if not aliases:
        return

    white_match = _build_alias_match_clause("white", aliases, params, "not_my_white_alias")
    black_match = _build_alias_match_clause("black", aliases, params, "not_my_black_alias")
    clauses.append(
        f"NOT ({white_match} OR {black_match})"
    )


def load_games(
    connection: sqlite3.Connection,
    database_id: int | None = None,
    game_number: int | None = None,
    player: str = "",
    color: str = "Either",
    result: str = "Any",
    eco_prefix: str = "",
    quality_filter: str = "All games",
    usernames: str = "peletis",
    limit: int = 200,
) -> pd.DataFrame:
    clauses: list[str] = []
    params: dict[str, object] = {"limit": limit}
    aliases = normalize_aliases(usernames)

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

    if quality_filter == "Missing result":
        clauses.append("(result IS NULL OR TRIM(result) = '' OR result = '*')")
    elif quality_filter == "Missing moves":
        clauses.append("(moves_san IS NULL OR TRIM(moves_san) = '')")
    elif quality_filter == "Not my game":
        _append_not_my_game_clause(clauses, params, aliases)

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


def load_quality_counts(connection: sqlite3.Connection, usernames: str) -> dict[str, int]:
    aliases = normalize_aliases(usernames)
    params: dict[str, object] = {}
    clauses: list[str] = []
    _append_not_my_game_clause(clauses, params, aliases)
    not_my_game_where = f"WHERE {' AND '.join(clauses)}" if clauses else "WHERE 1 = 0"

    counts = {
        "Missing result": connection.execute(
            """
            SELECT COUNT(*)
            FROM games
            WHERE result IS NULL OR TRIM(result) = '' OR result = '*'
            """
        ).fetchone()[0],
        "Missing moves": connection.execute(
            """
            SELECT COUNT(*)
            FROM games
            WHERE moves_san IS NULL OR TRIM(moves_san) = ''
            """
        ).fetchone()[0],
        "Not my game": connection.execute(
            f"""
            SELECT COUNT(*)
            FROM games
            {not_my_game_where}
            """,
            params,
        ).fetchone()[0],
    }
    return counts


def load_player_summary(connection: sqlite3.Connection, usernames: str) -> dict[str, int]:
    aliases = normalize_aliases(usernames)
    if not aliases:
        return {
            "white_games": 0,
            "black_games": 0,
            "total_games": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
        }

    params: dict[str, object] = {}
    white_match = _build_alias_match_clause("white", aliases, params, "summary_white_alias")
    black_match = _build_alias_match_clause("black", aliases, params, "summary_black_alias")
    player_match = f"({white_match} OR {black_match})"

    row = connection.execute(
        f"""
        SELECT
            SUM(CASE WHEN {white_match} THEN 1 ELSE 0 END) AS white_games,
            SUM(CASE WHEN {black_match} THEN 1 ELSE 0 END) AS black_games,
            SUM(CASE WHEN {player_match} THEN 1 ELSE 0 END) AS total_games,
            SUM(
                CASE
                    WHEN {white_match} AND result = '1-0' THEN 1
                    WHEN {black_match} AND result = '0-1' THEN 1
                    ELSE 0
                END
            ) AS wins,
            SUM(CASE WHEN {player_match} AND result = '1/2-1/2' THEN 1 ELSE 0 END) AS draws,
            SUM(
                CASE
                    WHEN {white_match} AND result = '0-1' THEN 1
                    WHEN {black_match} AND result = '1-0' THEN 1
                    ELSE 0
                END
            ) AS losses
        FROM games
        """,
        params,
    ).fetchone()

    return {
        "white_games": row["white_games"] or 0,
        "black_games": row["black_games"] or 0,
        "total_games": row["total_games"] or 0,
        "wins": row["wins"] or 0,
        "draws": row["draws"] or 0,
        "losses": row["losses"] or 0,
    }
