from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.aliases import load_alias_table, resolve_player_aliases
from src.db import DEFAULT_DB_PATH, database_has_required_schema, get_connection, initialize_database
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
    format_position_label,
    render_clickable_move_summary,
    render_game_summary,
    render_player_summary,
    render_quality_summary,
)

PLAYER_USERNAMES = "peletis"


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

    st.markdown(f"**Current position:** {position_label}")
    if move_sequence:
        nav_columns = st.columns([1, 1, 6])
        if nav_columns[0].button("Back"):
            st.session_state["move_sequence"] = st.session_state["move_sequence"][:-1]
            st.rerun()
        if nav_columns[1].button("Reset"):
            st.session_state["move_sequence"] = []
            st.rerun()

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
    st.markdown("<div style='margin-top: 1.15rem; margin-bottom: 0.35rem; font-weight: 700;'>Move breakdown</div>", unsafe_allow_html=True)
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

    with st.sidebar:
        page = st.radio("Page", ["Opening explorer", "Data review"])

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
