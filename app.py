from __future__ import annotations

from pathlib import Path

import chess
import pandas as pd
import streamlit as st

from import_pgn import DEFAULT_PGN_PATH, import_archive
from src.aliases import load_alias_table, resolve_player_aliases
from src.db import DEFAULT_DB_PATH, database_has_required_schema, get_connection, initialize_database
from src.move_text import parse_move_text
from src.pgn_source import get_eco_by_game_number, load_pgn_source_session, save_eco_updates, validate_eco
from src.queries import (
    load_data_review_counts,
    load_data_review_games,
    load_game_by_id,
    load_games,
    load_games_by_position,
    load_move_summary_by_position,
    load_move_summary,
    load_next_moves_by_position,
    load_pgn_export,
    load_player_summary,
    load_quality_counts,
)
from src.viewer import (
    build_board_from_san_sequence,
    format_position_label,
    render_clickable_move_summary,
    render_board,
    render_game_summary,
    render_player_summary,
    render_quality_summary,
)

PLAYER_USERNAMES = "peletis"


def _get_db_version_token() -> int:
    try:
        return DEFAULT_DB_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


@st.cache_data(show_spinner=False)
def _load_quality_counts_cached(_db_version: int, usernames: str) -> dict[str, int]:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_quality_counts(connection, usernames)


@st.cache_data(show_spinner=False)
def _load_player_summary_cached(
    _db_version: int,
    usernames: str,
    move_sequence: tuple[str, ...],
    position_label: str,
    player: str,
    color: str,
    result: str,
    eco_prefix: str,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_player_summary(
            connection=connection,
            usernames=usernames,
            move_sequence=move_sequence,
            position_label=position_label,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
        )


@st.cache_data(show_spinner=False)
def _load_move_summary_cached(
    _db_version: int,
    usernames: str,
    side: str,
    move_sequence: tuple[str, ...],
    player: str,
    color: str,
    result: str,
    eco_prefix: str,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_move_summary(
            connection=connection,
            usernames=usernames,
            side=side,
            move_sequence=move_sequence,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
        )


@st.cache_data(show_spinner=False)
def _load_move_summary_by_position_cached(
    _db_version: int,
    fen: str,
    usernames: str,
    side: str,
    player: str,
    color: str,
    result: str,
    eco_prefix: str,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_move_summary_by_position(
            connection=connection,
            fen=fen,
            usernames=usernames,
            side=side,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
        )


@st.cache_data(show_spinner=False)
def _load_games_cached(
    _db_version: int,
    move_sequence: tuple[str, ...],
    player: str,
    color: str,
    result: str,
    eco_prefix: str,
    usernames: str,
    limit: int,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_games(
            connection=connection,
            move_sequence=move_sequence,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
            usernames=usernames,
            limit=limit,
        )


@st.cache_data(show_spinner=False)
def _load_games_by_position_cached(
    _db_version: int,
    fen: str,
    limit: int,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_games_by_position(connection, fen, limit=limit)


@st.cache_data(show_spinner=False)
def _load_next_moves_by_position_cached(
    _db_version: int,
    fen: str,
) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as connection:
        return load_next_moves_by_position(connection, fen)


def _get_pending_eco_updates() -> dict[int, str]:
    pending = st.session_state.get("pending_eco_updates")
    if pending is None:
        pending = {}
        st.session_state["pending_eco_updates"] = pending
    return pending


def _load_or_get_pgn_session(force_reload: bool = False):
    if force_reload or "pgn_source_session" not in st.session_state:
        st.session_state["pgn_source_session"] = load_pgn_source_session(DEFAULT_PGN_PATH)
    return st.session_state["pgn_source_session"]


def _sync_opening_move_text(move_sequence: tuple[str, ...]) -> str:
    move_text = format_position_label(move_sequence)
    if st.session_state.get("opening_move_text_synced_sequence") != move_sequence:
        st.session_state["opening_move_text"] = move_text
        st.session_state["opening_move_text_synced_sequence"] = move_sequence
    return move_text


def _render_missing_eco_editor(review_df: pd.DataFrame) -> None:
    st.subheader("Batch ECO editor")
    status_message = st.session_state.pop("eco_editor_status", "")
    if status_message:
        st.success(status_message)

    if not DEFAULT_PGN_PATH.exists():
        st.warning(f"PGN source not found: {DEFAULT_PGN_PATH}")
        return

    try:
        source_session = _load_or_get_pgn_session()
    except OSError as exc:
        st.error(f"Could not load PGN source: {exc}")
        return

    pending_updates = _get_pending_eco_updates()
    eco_by_game_number = get_eco_by_game_number(source_session)

    action_columns = st.columns([1.3, 1.5, 1.5, 3.7])
    if action_columns[0].button("Reload source", key="reload_eco_source"):
        st.session_state["pgn_source_session"] = load_pgn_source_session(DEFAULT_PGN_PATH)
        source_session = st.session_state["pgn_source_session"]
        eco_by_game_number = get_eco_by_game_number(source_session)
        st.rerun()

    if action_columns[1].button("Save ECOs to PGN", key="save_eco_source"):
        if not pending_updates:
            st.info("No staged ECO updates to save.")
        else:
            try:
                updated_session = save_eco_updates(source_session, pending_updates)
            except (OSError, RuntimeError, ValueError) as exc:
                st.error(str(exc))
            else:
                st.session_state["pgn_source_session"] = updated_session
                st.session_state["pending_eco_updates"] = {}
                st.session_state["eco_editor_status"] = (
                    f"Saved {len(pending_updates)} ECO update(s) to {DEFAULT_PGN_PATH}. "
                    "Rebuild the database when ready."
                )
                st.rerun()

    if action_columns[2].button("Rebuild database", key="rebuild_database_from_source"):
        progress_container = st.container()
        progress_text = progress_container.empty()
        progress_bar = progress_container.progress(0.0)

        def render_import_progress(parsed_games: int, total_games: int | None, elapsed_seconds: float) -> None:
            if total_games:
                progress_bar.progress(min(parsed_games / total_games, 1.0))
                progress_text.caption(
                    f"Parsed {parsed_games:,}/{total_games:,} games in {elapsed_seconds:.1f}s..."
                )
            else:
                progress_bar.progress(0.0)
                progress_text.caption(f"Parsed {parsed_games:,} games in {elapsed_seconds:.1f}s...")

        def render_import_status(message: str) -> None:
            progress_text.caption(message)

        try:
            imported_games = import_archive(
                DEFAULT_PGN_PATH,
                DEFAULT_DB_PATH,
                progress_callback=render_import_progress,
                status_callback=render_import_status,
            )
        except Exception as exc:  # pragma: no cover - surfaced directly in UI
            progress_bar.empty()
            st.error(f"Rebuild failed: {exc}")
        else:
            progress_bar.progress(1.0)
            st.session_state["pgn_source_session"] = load_pgn_source_session(DEFAULT_PGN_PATH)
            st.session_state["eco_editor_status"] = f"Rebuilt the database from source with {imported_games:,} game(s)."
            st.rerun()

    action_columns[3].caption(
        f"Staged ECO updates: {len(pending_updates)}. "
        "Saving updates the source PGN only. Rebuild the database separately when you want the queue refreshed."
    )

    editor_df = review_df.copy()
    editor_df["source_eco"] = editor_df["game_number"].map(eco_by_game_number).fillna("")
    editor_df["new_eco"] = [
        pending_updates.get(int(game_number), str(source_eco or "").strip())
        for game_number, source_eco in zip(editor_df["game_number"], editor_df["source_eco"], strict=False)
    ]

    edited_df = st.data_editor(
        editor_df[["game_number", "source_line", "date", "white", "black", "result", "source_eco", "new_eco"]],
        use_container_width=True,
        hide_index=True,
        disabled=["game_number", "source_line", "date", "white", "black", "result", "source_eco"],
        column_config={
            "game_number": st.column_config.NumberColumn("Game Number", format="%d"),
            "source_line": st.column_config.NumberColumn("Source Line", format="%d"),
            "date": "Date",
            "white": "White",
            "black": "Black",
            "result": "Result",
            "source_eco": "Source ECO",
            "new_eco": st.column_config.TextColumn("New ECO"),
        },
        key="missing_eco_editor",
    )

    next_updates: dict[int, str] = {}
    validation_errors: list[str] = []
    for row in edited_df.itertuples(index=False):
        raw_value = str(row.new_eco or "").strip()
        if not raw_value:
            continue
        try:
            next_updates[int(row.game_number)] = validate_eco(raw_value)
        except ValueError:
            validation_errors.append(f"Game {int(row.game_number)}: `{raw_value}` is not a valid ECO.")

    st.session_state["pending_eco_updates"] = next_updates
    if validation_errors:
        st.error(" ".join(validation_errors[:10]))
    elif next_updates:
        st.caption(f"{len(next_updates)} ECO update(s) currently staged.")

    if not review_df.empty:
        source_only_games = int((editor_df["source_eco"].fillna("").str.strip() != "").sum())
        if source_only_games:
            st.info(
                f"{source_only_games} game(s) in this queue already have an ECO in `all.pgn` but still appear here "
                "because the database has not been rebuilt yet."
            )


def _render_game_detail_only(connection, games_df: pd.DataFrame) -> None:
    if games_df.empty:
        st.info("No games matched the current filters.")
        return

    options = {
        (
            f"game {row.game_number} | line {row.source_line} | "
            f"{row.date} | {row.white} vs {row.black} | {row.result}"
        ): int(row.id)
        for row in games_df.itertuples(index=False)
    }
    selected_label = st.selectbox("Select a game", list(options.keys()))
    selected_game = load_game_by_id(connection, options[selected_label])

    if selected_game is not None:
        render_game_summary(dict(selected_game))


def render_opening_explorer(connection) -> None:
    with st.sidebar:
        st.header("Filters")
        player = st.text_input("Player")
        color = st.selectbox("Colour", ["Any", "White", "Black"])
        result = st.selectbox("Result", ["Any", "1-0", "0-1", "1/2-1/2", "*"])
        eco_prefix = st.text_input("ECO starts with")
        limit = st.slider("Max rows", min_value=25, max_value=500, value=200, step=25)

    move_sequence = tuple(st.session_state["move_sequence"])
    current_move_text = _sync_opening_move_text(move_sequence)

    entered_move_text = st.session_state.get("opening_move_text", current_move_text)
    move_text_error = ""
    if entered_move_text != current_move_text:
        try:
            move_sequence = parse_move_text(entered_move_text)
        except ValueError as exc:
            move_text_error = str(exc)
        else:
            st.session_state["move_sequence"] = list(move_sequence)
            st.session_state["opening_move_text_synced_sequence"] = move_sequence

    db_version = _get_db_version_token()
    position_label = format_position_label(move_sequence)
    critical_counts = _load_quality_counts_cached(db_version, PLAYER_USERNAMES)
    active_critical = {label: value for label, value in critical_counts.items() if value > 0}
    resolved_player_aliases = resolve_player_aliases(player)

    if active_critical:
        warning_text = ", ".join(f"{label}: {value:,}" for label, value in active_critical.items())
        st.warning(f"Critical issues need review: {warning_text}")

    if resolved_player_aliases["expanded"]:
        alias_text = ", ".join(resolved_player_aliases["display_aliases"])
        st.info(f"Player aliases: {resolved_player_aliases['canonical_name']} -> {alias_text}")

    render_player_summary(
        _load_player_summary_cached(
            db_version,
            PLAYER_USERNAMES,
            move_sequence,
            position_label,
            player,
            color,
            result,
            eco_prefix,
        )
    )
    st.markdown("<div style='height: 1.8rem;'></div>", unsafe_allow_html=True)

    move_side = "total" if color == "Any" else color.lower()
    board_column, left_gap_column, controls_column, right_gap_column, moves_column = st.columns([1.28, 0.08, 0.22, 0.08, 1.0])
    current_fen = ""

    with board_column:
        try:
            board, last_move = build_board_from_san_sequence(move_sequence)
        except ValueError as exc:
            st.warning(f"Could not render board for the current move path: {exc}")
        else:
            current_fen = board.fen()
            render_board(board, last_move=last_move, size=520)

    with controls_column:
        st.markdown("<div style='height: 0.65rem;'></div>", unsafe_allow_html=True)
        if st.button("↻", key="rotate_opening_board", help="Rotate board", use_container_width=True):
            st.session_state["board_orientation"] = (
                "Black" if st.session_state["board_orientation"] == "White" else "White"
            )
            st.rerun()
        if st.button("Back", key="opening_back", disabled=not move_sequence, use_container_width=True):
            st.session_state["move_sequence"] = st.session_state["move_sequence"][:-1]
            st.rerun()
        if st.button("Reset", key="opening_reset", disabled=not move_sequence, use_container_width=True):
            st.session_state["move_sequence"] = []
            st.rerun()

    with moves_column:
        with st.container(height=540):
            if current_fen:
                move_summary_df = _load_move_summary_by_position_cached(
                    db_version,
                    current_fen,
                    PLAYER_USERNAMES,
                    move_side,
                    player,
                    color,
                    result,
                    eco_prefix,
                )
            else:
                move_summary_df = pd.DataFrame(columns=["move", "games", "white", "draw", "black"])

            selected_move = render_clickable_move_summary(
                move_summary_df,
                ply_index=len(move_sequence),
                key_prefix=f"position_move_{len(move_sequence)}_{color}_{player}_{result}_{eco_prefix}",
                show_move_prefix=False,
            )
    entered_move_text = st.text_input(
        "Moves",
        value=st.session_state.get("opening_move_text", current_move_text),
        key="opening_move_text",
        label_visibility="collapsed",
        placeholder="Enter moves and press Enter",
    )
    if move_text_error:
        st.warning(move_text_error)
    if selected_move is not None:
        st.session_state["move_sequence"] = [*move_sequence, selected_move]
        st.rerun()

    games_df = _load_games_cached(
        db_version,
        move_sequence,
        player,
        color,
        result,
        eco_prefix,
        PLAYER_USERNAMES,
        limit,
    )

    st.subheader("Recent games")
    render_game_list_and_detail(connection, games_df)


def render_game_list_and_detail(connection, games_df: pd.DataFrame) -> None:
    export_columns = st.columns([1, 1, 6])
    export_columns[0].download_button(
        "Export CSV",
        data=games_df.drop(columns=["id"]).to_csv(index=False),
        file_name="games_export.csv",
        mime="text/csv",
    )
    export_columns[1].download_button(
        "Export PGN",
        data=load_pgn_export(connection, games_df["id"].tolist()),
        file_name="games_export.pgn",
        mime="application/x-chess-pgn",
    )

    st.dataframe(games_df.drop(columns=["id"]), use_container_width=True, hide_index=True)

    if games_df.empty:
        st.info("No games matched the current filters.")
        return

    options = {
        (
            f"game {row.game_number} | line {row.source_line} | "
            f"{row.date} | {row.white} vs {row.black} | {row.result}"
        ): int(row.id)
        for row in games_df.itertuples(index=False)
    }
    selected_label = st.selectbox("Select a game", list(options.keys()))
    selected_game = load_game_by_id(connection, options[selected_label])

    if selected_game is not None:
        render_game_summary(dict(selected_game))


def render_position_explorer(connection) -> None:
    default_fen = st.session_state.get("position_explorer_fen", chess.STARTING_FEN)

    with st.sidebar:
        st.header("Position explorer")
        limit = st.slider("Max rows", min_value=25, max_value=500, value=200, step=25, key="position_limit")

    fen_text = st.text_area(
        "FEN",
        value=default_fen,
        key="position_explorer_fen",
        height=80,
        placeholder="Paste a FEN here",
    ).strip()

    if not fen_text:
        st.info("Paste a FEN to explore the stored positions table.")
        return

    try:
        board = chess.Board(fen_text)
    except ValueError as exc:
        st.warning(f"Invalid FEN: {exc}")
        return

    db_version = _get_db_version_token()
    next_moves_df = _load_next_moves_by_position_cached(db_version, fen_text)
    games_df = _load_games_by_position_cached(db_version, fen_text, limit)

    board_column, moves_column = st.columns([1.18, 1.0])
    with board_column:
        render_board(board, size=520)
    with moves_column:
        st.subheader("Next moves")
        if next_moves_df.empty:
            st.info("No stored next moves for this position.")
        else:
            st.dataframe(next_moves_df, use_container_width=True, hide_index=True)

    st.subheader("Matching games")
    render_game_list_and_detail(connection, games_df)


def render_data_review(connection) -> None:
    data_review_counts = load_data_review_counts(connection)
    data_quality_counts = load_quality_counts(connection, PLAYER_USERNAMES)
    queue_options = ["Missing date", "Missing ECO"]
    default_queue = "Missing date"
    for queue_name in queue_options:
        if data_review_counts[queue_name] > 0:
            default_queue = queue_name
            break

    with st.sidebar:
        st.header("Data review")
        review_type = st.selectbox("Queue", queue_options, index=queue_options.index(default_queue))
        limit = st.slider("Max rows", min_value=25, max_value=500, value=200, step=25, key="data_review_limit")

    st.subheader("Critical issues")
    render_quality_summary(data_quality_counts)

    st.subheader("Data quality")
    render_quality_summary(data_review_counts)

    review_df = load_data_review_games(connection, review_type=review_type, limit=limit)
    st.markdown(f"**{review_type} games**")
    if review_df.empty:
        st.info(f"No games are currently in the `{review_type}` queue.")
    elif review_type == "Missing ECO":
        _render_missing_eco_editor(review_df)
        _render_game_detail_only(connection, review_df)
    else:
        render_game_list_and_detail(connection, review_df)

    alias_df = load_alias_table()
    if not alias_df.empty:
        st.subheader("Aliases")
        st.dataframe(alias_df, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Opening Explorer", layout="wide")
    st.markdown(
        """
        <style>
        h1 {
            text-align: center;
        }
        div.stButton > button {
            background: #e4f0e2;
            border: 1px solid #b7cfb3;
            border-radius: 0.45rem;
            color: #223222;
            font-size: 0.95rem;
            font-weight: 500;
            line-height: 1.15;
            min-height: 2rem;
            padding: 0.2rem 0.65rem;
            white-space: nowrap;
        }
        div.stButton > button:hover {
            background: #d5e7d2;
            border-color: #9fbe9a;
            color: #182618;
        }
        div.stButton > button[kind="secondary"] {
            background: #eef3e3;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "move_sequence" not in st.session_state:
        st.session_state["move_sequence"] = []
    if "board_orientation" not in st.session_state:
        st.session_state["board_orientation"] = "White"

    with st.sidebar:
        page = st.radio("Page", ["Opening explorer", "Position explorer", "Data review"])

    title = {
        "Opening explorer": "Opening Explorer",
        "Position explorer": "Position Explorer",
        "Data review": "Data review",
    }[page]
    st.title(title)

    db_path = Path("data/games.db")
    db_exists = db_path.exists()

    with get_connection(DEFAULT_DB_PATH) as connection:
        initialize_database(connection)

        if not db_exists:
            st.warning("No database found yet. Run `python import_pgn.py` first.")
            return

        if not database_has_required_schema(connection):
            st.warning(
                "The database was built with an older schema. Run `python import_pgn.py --pgn pgn/all.pgn` to rebuild it."
            )
            return

        if page == "Opening explorer":
            render_opening_explorer(connection)
        elif page == "Position explorer":
            render_position_explorer(connection)
        else:
            render_data_review(connection)


if __name__ == "__main__":
    main()
