from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from import_pgn import DEFAULT_PGN_PATH, import_archive
from src.aliases import load_alias_table, resolve_player_aliases
from src.db import DEFAULT_DB_PATH, database_has_required_schema, get_connection, initialize_database
from src.pgn_source import get_eco_by_game_number, load_pgn_source_session, save_eco_updates, validate_eco
from src.queries import (
    load_data_review_counts,
    load_data_review_games,
    load_game_by_id,
    load_games,
    load_move_summary,
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
        game_number_text = st.text_input("Game Number")
        player = st.text_input("Player")
        color = st.selectbox("Colour", ["Any", "White", "Black"])
        result = st.selectbox("Result", ["Any", "1-0", "0-1", "1/2-1/2", "*"])
        eco_prefix = st.text_input("ECO starts with")
        limit = st.slider("Max rows", min_value=25, max_value=500, value=200, step=25)

    game_number = int(game_number_text) if game_number_text.strip().isdigit() else None
    move_sequence = tuple(st.session_state["move_sequence"])
    position_label = format_position_label(move_sequence)
    critical_counts = load_quality_counts(connection, PLAYER_USERNAMES)
    active_critical = {label: value for label, value in critical_counts.items() if value > 0}
    resolved_player_aliases = resolve_player_aliases(player)

    if active_critical:
        warning_text = ", ".join(f"{label}: {value:,}" for label, value in active_critical.items())
        st.warning(f"Critical issues need review: {warning_text}")

    if resolved_player_aliases["expanded"]:
        alias_text = ", ".join(resolved_player_aliases["display_aliases"])
        st.info(f"Player aliases: {resolved_player_aliases['canonical_name']} -> {alias_text}")

    render_player_summary(
        load_player_summary(
            connection=connection,
            usernames=PLAYER_USERNAMES,
            game_number=game_number,
            move_sequence=move_sequence,
            position_label=position_label,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
        )
    )

    try:
        board, last_move = build_board_from_san_sequence(move_sequence)
    except ValueError as exc:
        st.warning(f"Could not render board for the current move path: {exc}")
    else:
        render_board(board, last_move=last_move, size=520)
        if position_label:
            st.markdown(f"<div style='text-align:center; font-weight:600;'>{position_label}</div>", unsafe_allow_html=True)
        if move_sequence:
            left_pad, back_column, reset_column, right_pad = st.columns([3, 1, 1, 3])
            if back_column.button("Back"):
                st.session_state["move_sequence"] = st.session_state["move_sequence"][:-1]
                st.rerun()
            if reset_column.button("Reset"):
                st.session_state["move_sequence"] = []
                st.rerun()

    move_side = "total" if color == "Any" else color.lower()
    selected_move = render_clickable_move_summary(
        load_move_summary(
            connection=connection,
            usernames=PLAYER_USERNAMES,
            side=move_side,
            game_number=game_number,
            move_sequence=move_sequence,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
        ),
        ply_index=len(move_sequence),
        key_prefix=f"move_{'__'.join(move_sequence) or 'start'}_{color}_{player}_{result}_{eco_prefix}",
    )
    if selected_move is not None:
        st.session_state["move_sequence"] = [*st.session_state["move_sequence"], selected_move]
        st.rerun()

    games_df = load_games(
        connection=connection,
        game_number=game_number,
        move_sequence=move_sequence,
        player=player,
        color=color,
        result=result,
        eco_prefix=eco_prefix,
        usernames=PLAYER_USERNAMES,
        limit=limit,
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
        page = st.radio("Page", ["Opening explorer", "Data review"])
        st.selectbox("Board bottom", ["White", "Black"], key="board_orientation")

    st.title("Opening Explorer" if page == "Opening explorer" else "Data review")

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
        else:
            render_data_review(connection)


if __name__ == "__main__":
    main()
