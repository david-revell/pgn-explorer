from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.db import DEFAULT_DB_PATH, database_has_required_schema, get_connection, initialize_database
from src.queries import load_game_by_id, load_games, load_move_summary, load_player_summary, load_quality_counts
from src.viewer import (
    format_position_label,
    render_clickable_move_summary,
    render_game_summary,
    render_player_summary,
    render_quality_summary,
)

PLAYER_USERNAMES = "peletis"


def main() -> None:
    st.set_page_config(page_title="Opening Explorer", layout="wide")
    st.title("Opening Explorer")
    st.caption("Search and review a local PGN archive.")
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

        st.subheader("Data Quality")
        render_quality_summary(load_quality_counts(connection, PLAYER_USERNAMES))

        st.subheader("Position summary")
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

        st.subheader("Games")
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


if __name__ == "__main__":
    main()
