from __future__ import annotations

import re
import sqlite3

import pandas as pd

from src.aliases import resolve_player_aliases
from src.positions import normalize_fen


def _is_eco_input(value: str) -> bool:
    """Return True if value looks like an ECO code prefix (e.g. 'C', 'C6', 'C65')."""
    return bool(re.fullmatch(r"[A-Ea-e]\d{0,2}", value.strip()))


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
    return f"{field_name} IN ({alias_sql})"


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


def _append_player_clause(
    clauses: list[str],
    params: dict[str, object],
    player: str,
    color: str = "Any",
) -> None:
    """Append a WHERE clause filtering games by player name.

    If the player text matches a known alias group, expands to all known
    variants using the pre-normalised white_norm/black_norm columns.

    Otherwise, matches are case-insensitive against the raw white/black columns:
    - Exact match by default (e.g. "Magnus" will not match "Magnus Carlsen")
    - % acts as a wildcard (e.g. "%Magnus%" matches any name containing "Magnus")

    When color is "White" or "Black", the match is restricted to that side,
    so the colour filter refers to the typed player rather than the app owner.
    """
    resolved = resolve_player_aliases(player)
    if resolved["expanded"]:
        search_names = resolved["search_names"]
        placeholders: list[str] = []
        for index, search_name in enumerate(search_names):
            key = f"player_alias_{index}"
            params[key] = search_name
            placeholders.append(f":{key}")

        alias_sql = ", ".join(placeholders)
        if color == "White":
            clauses.append(f"white_norm IN ({alias_sql})")
        elif color == "Black":
            clauses.append(f"black_norm IN ({alias_sql})")
        else:
            clauses.append(f"(white_norm IN ({alias_sql}) OR black_norm IN ({alias_sql}))")
        return

    term = player.strip().lower()
    if "%" in term:
        params["player"] = term
        if color == "White":
            clauses.append("LOWER(white) LIKE :player")
        elif color == "Black":
            clauses.append("LOWER(black) LIKE :player")
        else:
            clauses.append("(LOWER(white) LIKE :player OR LOWER(black) LIKE :player)")
    else:
        params["player"] = term
        if color == "White":
            clauses.append("LOWER(white) = :player")
        elif color == "Black":
            clauses.append("LOWER(black) = :player")
        else:
            clauses.append("(LOWER(white) = :player OR LOWER(black) = :player)")


def _append_shared_game_filters(
    clauses: list[str],
    params: dict[str, object],
    aliases: list[str],
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    opening: str = "",
    quality_filter: str = "All games",
) -> None:
    if game_number is not None:
        clauses.append("game_number = :game_number")
        params["game_number"] = game_number

    if move_sequence:
        move_text = " ".join(move_sequence)
        clauses.append(
            "(moves_san = :move_text OR (moves_san >= :move_prefix_start AND moves_san < :move_prefix_end))"
        )
        params["move_text"] = move_text
        params["move_prefix_start"] = f"{move_text} "
        params["move_prefix_end"] = f"{move_text} \uffff"

    if player.strip():
        _append_player_clause(clauses, params, player, color)

    if result != "Any":
        clauses.append("result = :result")
        params["result"] = result

    if opening and opening.strip():
        term = opening.strip()
        if _is_eco_input(term):
            clauses.append("eco LIKE :eco_prefix")
            params["eco_prefix"] = f"{term.upper()}%"
        else:
            clauses.append("LOWER(final_opening_name) LIKE :opening_name")
            params["opening_name"] = f"%{term.lower()}%"

    if quality_filter == "Missing result":
        clauses.append("(result IS NULL OR TRIM(result) = '' OR result = '*')")
    elif quality_filter == "Missing moves":
        clauses.append("(moves_san IS NULL OR moves_san = '')")
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
    opening: str = "",
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
        opening=opening,
        quality_filter=quality_filter,
    )

    if not player.strip():
        if color == "White" and aliases:
            clauses.append(_build_alias_match_clause("white_norm", aliases, params, "games_white_alias"))
        elif color == "Black" and aliases:
            clauses.append(_build_alias_match_clause("black_norm", aliases, params, "games_black_alias"))

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    query = f"""
        SELECT
            id, game_number, source_line, date, white, black, result, eco,
            white_elo, black_elo, event, site
        FROM games
        {where_sql}
        ORDER BY
            CASE WHEN date_sort_key = 0 THEN 1 ELSE 0 END ASC,
            date_sort_key DESC,
            date_precision ASC,
            game_number DESC
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


def load_pgn_export(connection: sqlite3.Connection, game_ids: list[int]) -> str:
    if not game_ids:
        return ""

    placeholders = ", ".join("?" for _ in game_ids)
    rows = connection.execute(
        f"""
        SELECT id, pgn_text
        FROM games
        WHERE id IN ({placeholders})
        """,
        game_ids,
    ).fetchall()

    pgn_by_id = {int(row["id"]): row["pgn_text"] for row in rows}
    ordered_pgns = [pgn_by_id[game_id].strip() for game_id in game_ids if game_id in pgn_by_id]
    return "\n\n".join(ordered_pgns) + ("\n" if ordered_pgns else "")


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
            WHERE moves_san IS NULL OR moves_san = ''
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


def load_data_review_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "Missing date": connection.execute(
            """
            SELECT COUNT(*)
            FROM games
            WHERE date IS NULL OR TRIM(date) = '' OR TRIM(date) = '????.??.??'
            """
        ).fetchone()[0],
        "Missing ECO": connection.execute(
            """
            SELECT COUNT(*)
            FROM games
            WHERE eco IS NULL OR TRIM(eco) = ''
            """
        ).fetchone()[0],
    }


def load_data_review_games(
    connection: sqlite3.Connection,
    review_type: str,
    limit: int = 200,
) -> pd.DataFrame:
    if review_type == "Missing date":
        where_sql = "date IS NULL OR TRIM(date) = '' OR TRIM(date) = '????.??.??'"
        reason_sql = "'Missing date'"
    else:
        where_sql = "eco IS NULL OR TRIM(eco) = ''"
        reason_sql = "'Missing ECO'"

    query = f"""
        SELECT
            id,
            game_number,
            source_line,
            date,
            white,
            black,
            result,
            eco,
            {reason_sql} AS reason
        FROM games
        WHERE {where_sql}
        ORDER BY game_number DESC
        LIMIT :limit
    """
    return pd.read_sql_query(query, connection, params={"limit": limit})


def _build_stats_where_clause(
    usernames: str,
    prefix: str,
    side: str,
    game_number: int | None = None,
    move_sequence: tuple[str, ...] = (),
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    opening: str = "",
) -> tuple[str, dict[str, object]]:
    aliases = normalize_aliases(usernames)
    if not aliases:
        return "WHERE 1 = 0", {}

    params: dict[str, object] = {}
    clauses: list[str] = []
    white_match = _build_alias_match_clause("white_norm", aliases, params, f"{prefix}_white_alias")
    black_match = _build_alias_match_clause("black_norm", aliases, params, f"{prefix}_black_alias")

    # Add result, opening, move sequence filters — but not the player filter,
    # which is handled separately below so the side constraint can be applied correctly.
    _append_shared_game_filters(
        clauses=clauses,
        params=params,
        aliases=aliases,
        game_number=game_number,
        move_sequence=move_sequence,
        player="",
        color="Any",
        result=result,
        opening=opening,
    )

    if player.strip():
        # Side constraint refers to the typed player, not the app owner.
        side_color = {"white": "White", "black": "Black"}.get(side, "Any")
        _append_player_clause(clauses, params, player, side_color)
    else:
        # No player typed: side constraint refers to the app owner's aliases.
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
    opening: str = "",
) -> pd.DataFrame:
    rows: list[dict[str, int | str]] = []

    if color == "Any":
        total_where_sql, total_params = _build_stats_where_clause(
            usernames, "summary_total", "total", game_number, move_sequence, player, color, result, opening
        )
        total_row = {"Colour": "Total", "Position": position_label, **_load_result_summary(connection, total_where_sql, total_params)}
    else:
        total_row = None

    if color in {"Any", "White"}:
        white_where_sql, white_params = _build_stats_where_clause(
            usernames, "summary_white", "white", game_number, move_sequence, player, color, result, opening
        )
        rows.append({"Colour": "White", "Position": position_label, **_load_result_summary(connection, white_where_sql, white_params)})

    if color in {"Any", "Black"}:
        black_where_sql, black_params = _build_stats_where_clause(
            usernames, "summary_black", "black", game_number, move_sequence, player, color, result, opening
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
    opening: str = "",
) -> pd.DataFrame:
    where_sql, params = _build_stats_where_clause(
        usernames, f"move_summary_{side}", side, game_number, move_sequence, player, color, result, opening
    )
    query = f"""
        SELECT
            moves_san,
            result
        FROM games
        {where_sql} AND moves_san IS NOT NULL AND moves_san <> ''
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


def load_move_summary_by_position(
    connection: sqlite3.Connection,
    fen: str,
    usernames: str,
    side: str,
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    opening: str = "",
) -> pd.DataFrame:
    where_sql, params = _build_stats_where_clause(
        usernames, f"position_move_summary_{side}", side, None, (), player, color, result, opening
    )
    params["position_key"] = normalize_fen(fen)
    query = f"""
        SELECT
            p.next_move AS move,
            COUNT(*) AS games,
            SUM(CASE WHEN g.result = '1-0' THEN 1 ELSE 0 END) AS white,
            SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END) AS draw,
            SUM(CASE WHEN g.result = '0-1' THEN 1 ELSE 0 END) AS black
        FROM positions p
        INNER JOIN games g ON g.id = p.game_id
        {where_sql} AND p.position_key = :position_key AND p.next_move IS NOT NULL
        GROUP BY p.next_move
        ORDER BY games DESC, move ASC
    """
    return pd.read_sql_query(query, connection, params=params)


def load_games_by_position(
    connection: sqlite3.Connection,
    fen: str,
    player: str = "",
    color: str = "Any",
    result: str = "Any",
    opening: str = "",
    usernames: str = "peletis",
    limit: int = 200,
) -> pd.DataFrame:
    position_key = normalize_fen(fen)
    aliases = normalize_aliases(usernames)
    params: dict[str, object] = {"position_key": position_key, "limit": limit}
    clauses = ["p.position_key = :position_key"]

    if player.strip():
        _append_player_clause(clauses, params, player, color)

    if result != "Any":
        clauses.append("g.result = :result")
        params["result"] = result

    if opening and opening.strip():
        term = opening.strip()
        if _is_eco_input(term):
            clauses.append("g.eco LIKE :eco_prefix")
            params["eco_prefix"] = f"{term.upper()}%"
        else:
            clauses.append("LOWER(g.final_opening_name) LIKE :opening_name")
            params["opening_name"] = f"%{term.lower()}%"

    if not player.strip():
        if color == "White" and aliases:
            clauses.append(_build_alias_match_clause("g.white_norm", aliases, params, "position_games_white_alias"))
        elif color == "Black" and aliases:
            clauses.append(_build_alias_match_clause("g.black_norm", aliases, params, "position_games_black_alias"))

    where_sql = " AND ".join(clauses)

    query = f"""
        WITH matched_games AS (
            SELECT
                g.id,
                g.game_number,
                MIN(p.ply) AS ply,
                g.source_line,
                g.date,
                g.white,
                g.black,
                g.result,
                g.eco,
                g.white_elo,
                g.black_elo,
                g.event,
                g.site,
                g.date_sort_key,
                g.date_precision
            FROM positions p
            INNER JOIN games g ON g.id = p.game_id
            WHERE {where_sql}
            GROUP BY
                g.id,
                g.game_number,
                g.source_line,
                g.date,
                g.white,
                g.black,
                g.result,
                g.eco,
                g.white_elo,
                g.black_elo,
                g.event,
                g.site,
                g.date_sort_key,
                g.date_precision
        )
        SELECT
            id,
            game_number,
            ply,
            source_line,
            date,
            white,
            black,
            result,
            eco,
            white_elo,
            black_elo,
            event,
            site
        FROM matched_games
        ORDER BY
            CASE WHEN date_sort_key = 0 THEN 1 ELSE 0 END ASC,
            date_sort_key DESC,
            date_precision ASC,
            game_number DESC,
            ply ASC
        LIMIT :limit
    """
    return pd.read_sql_query(query, connection, params=params)


def load_next_moves_by_position(
    connection: sqlite3.Connection,
    fen: str,
) -> pd.DataFrame:
    position_key = normalize_fen(fen)
    query = """
        SELECT
            next_move AS move,
            COUNT(*) AS games
        FROM positions
        WHERE position_key = :position_key
          AND next_move IS NOT NULL
        GROUP BY next_move
        ORDER BY games DESC, move ASC
    """
    return pd.read_sql_query(query, connection, params={"position_key": position_key})


def load_opening_by_position(
    connection: sqlite3.Connection,
    fen: str,
) -> sqlite3.Row | None:
    position_key = normalize_fen(fen)
    return connection.execute(
        """
        SELECT eco, name, pgn, uci, position_key
        FROM opening_positions
        WHERE position_key = ?
        LIMIT 1
        """,
        (position_key,),
    ).fetchone()


def load_openings_by_position_keys(
    connection: sqlite3.Connection,
    position_keys: list[str],
) -> dict[str, sqlite3.Row]:
    if not position_keys:
        return {}

    placeholders = ", ".join("?" for _ in position_keys)
    rows = connection.execute(
        f"""
        SELECT position_key, eco, name, pgn, uci
        FROM opening_positions
        WHERE position_key IN ({placeholders})
        """,
        position_keys,
    ).fetchall()
    return {str(row["position_key"]): row for row in rows}
