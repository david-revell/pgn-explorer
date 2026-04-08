from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.db import DEFAULT_DB_PATH, database_has_required_schema, get_connection, initialize_database
from src.queries import load_first_move_summary, load_game_by_id, load_games, load_player_summary, load_quality_counts
from src.viewer import render_game_summary, render_move_summary, render_player_summary, render_quality_summary


def main() -> None:
    st.set_page_config(page_title="pgn-explorer", layout="wide")
    st.title("pgn-explorer")
    st.caption("Search and review a local PGN archive.")

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
            usernames = st.text_input("My usernames", value="peletis")
            quality_filter = st.selectbox(
                "Data quality",
                ["All games", "Missing result", "Missing moves", "Not my game"],
            )
            game_number_text = st.text_input("Game Number")
            player = st.text_input("Player")
            color = st.selectbox("Colour", ["Either", "White", "Black"])
            result = st.selectbox("Result", ["Any", "1-0", "0-1", "1/2-1/2", "*"])
            eco_prefix = st.text_input("ECO starts with")
            limit = st.slider("Max rows", min_value=25, max_value=500, value=200, step=25)

        game_number = int(game_number_text) if game_number_text.strip().isdigit() else None

        st.subheader("My Games")
        render_player_summary(load_player_summary(connection, usernames))
        st.markdown("**Next moves as White**")
        render_move_summary(load_first_move_summary(connection, usernames, "white"))
        st.markdown("**Next moves as Black**")
        render_move_summary(load_first_move_summary(connection, usernames, "black"))

        st.subheader("Data Quality")
        render_quality_summary(load_quality_counts(connection, usernames))

        games_df = load_games(
            connection=connection,
            game_number=game_number,
            player=player,
            color=color,
            result=result,
            eco_prefix=eco_prefix,
            quality_filter=quality_filter,
            usernames=usernames,
            limit=limit,
        )

        st.subheader("Games")
        st.dataframe(games_df, use_container_width=True, hide_index=True)

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
