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


def _append_shared_game_filters(
    clauses: list[str],
    params: dict[str, object],
    aliases: list[str],
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    eco_prefix: str = "",
    quality_filter: str = "All games",
) -> None:
    if game_number is not None:
        clauses.append("game_number = :game_number")
        params["game_number"] = game_number

    if move_sequence:
        move_text = " ".join(move_sequence)
        clauses.append("(TRIM(moves_san) = :move_text OR TRIM(moves_san) LIKE :move_prefix)")
        params["move_text"] = move_text
        params["move_prefix"] = f"{move_text} %"

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


def load_games(
    connection: sqlite3.Connection,
    database_id: int | None = None,
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
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

    _append_shared_game_filters(
        clauses=clauses,
        params=params,
        aliases=aliases,
        game_number=game_number,
        move_sequence=move_sequence,
        player=player,
        color=color,
        result=result,
        eco_prefix=eco_prefix,
        quality_filter=quality_filter,
    )

    if not player.strip() and color == "White" and aliases:
        clauses.append(_build_alias_match_clause("white", aliases, params, "games_white_alias"))
    elif not player.strip() and color == "Black" and aliases:
        clauses.append(_build_alias_match_clause("black", aliases, params, "games_black_alias"))

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


def _build_stats_where_clause(
    usernames: str,
    prefix: str,
    side: str,
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    eco_prefix: str = "",
) -> tuple[str, dict[str, object]]:
    aliases = normalize_aliases(usernames)
    if not aliases:
        return "WHERE 1 = 0", {}

    params: dict[str, object] = {}
    clauses: list[str] = []
    white_match = _build_alias_match_clause("white", aliases, params, f"{prefix}_white_alias")
    black_match = _build_alias_match_clause("black", aliases, params, f"{prefix}_black_alias")

    _append_shared_game_filters(
        clauses=clauses,
        params=params,
        aliases=aliases,
        game_number=game_number,
        move_sequence=move_sequence,
        player=player,
        color=color,
        result=result,
        eco_prefix=eco_prefix,
    )

    if side == "white":
        clauses.append(white_match)
    elif side == "black":
        clauses.append(black_match)
    else:
        clauses.append(f"({white_match} OR {black_match})")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _load_result_summary(connection: sqlite3.Connection, where_sql: str, params: dict[str, object]) -> dict[str, int]:
    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS games,
            SUM(CASE WHEN result = '1-0' THEN 1 ELSE 0 END) AS white,
            SUM(CASE WHEN result = '1/2-1/2' THEN 1 ELSE 0 END) AS draw,
            SUM(CASE WHEN result = '0-1' THEN 1 ELSE 0 END) AS black
        FROM games
        {where_sql}
        """,
        params,
    ).fetchone()

    return {
        "games": row["games"] or 0,
        "white": row["white"] or 0,
        "draw": row["draw"] or 0,
        "black": row["black"] or 0,
    }


def load_player_summary(
    connection: sqlite3.Connection,
    usernames: str,
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    position_label: str = "Start",
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    eco_prefix: str = "",
) -> pd.DataFrame:
    rows: list[dict[str, int | str]] = []

    if color == "Any":
        total_where_sql, total_params = _build_stats_where_clause(
            usernames, "summary_total", "total", game_number, move_sequence, player, color, result, eco_prefix
        )
        total_row = {"Colour": "Total", "Position": position_label, **_load_result_summary(connection, total_where_sql, total_params)}
    else:
        total_row = None

    if color in {"Any", "White"}:
        white_where_sql, white_params = _build_stats_where_clause(
            usernames, "summary_white", "white", game_number, move_sequence, player, color, result, eco_prefix
        )
        rows.append({"Colour": "White", "Position": position_label, **_load_result_summary(connection, white_where_sql, white_params)})

    if color in {"Any", "Black"}:
        black_where_sql, black_params = _build_stats_where_clause(
            usernames, "summary_black", "black", game_number, move_sequence, player, color, result, eco_prefix
        )
        rows.append({"Colour": "Black", "Position": position_label, **_load_result_summary(connection, black_where_sql, black_params)})

    if total_row is not None:
        rows.append(total_row)

    return pd.DataFrame(rows)


def load_move_summary(
    connection: sqlite3.Connection,
    usernames: str,
    side: str,
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    eco_prefix: str = "",
) -> pd.DataFrame:
    where_sql, params = _build_stats_where_clause(
        usernames, f"move_summary_{side}", side, game_number, move_sequence, player, color, result, eco_prefix
    )
    query = f"""
        SELECT
            moves_san,
            result
        FROM games
        {where_sql} AND moves_san IS NOT NULL AND TRIM(moves_san) <> ''
    """
    games_df = pd.read_sql_query(query, connection, params=params)
    if games_df.empty:
        return pd.DataFrame(columns=["move", "games", "white", "draw", "black"])

    next_move_index = len(move_sequence)
    rows: list[dict[str, int | str]] = []
    for row in games_df.itertuples(index=False):
        tokens = row.moves_san.strip().split()
        if len(tokens) <= next_move_index:
            continue

        rows.append(
            {
                "move": tokens[next_move_index],
                "result": row.result,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["move", "games", "white", "draw", "black"])

    moves_df = pd.DataFrame(rows)
    summary_df = (
        moves_df.groupby("move", as_index=False)
        .agg(
            games=("result", "size"),
            white=("result", lambda series: int((series == "1-0").sum())),
            draw=("result", lambda series: int((series == "1/2-1/2").sum())),
            black=("result", lambda series: int((series == "0-1").sum())),
        )
        .sort_values(["games", "move"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )
    return summary_df
