from __future__ import annotations

import streamlit as st


def render_game_summary(game: dict) -> None:
    st.subheader(f"{game['white']} vs {game['black']}")
    st.caption(
        f"{game['date']} | {game['result']} | ECO {game['eco'] or '?'} | {game['event'] or 'Unknown event'}"
    )

    st.write(
        {
            "Database ID": game["id"],
            "Game Number": game["game_number"],
            "Source Line": game["source_line"],
            "Site": game["site"],
            "Round": game["round"],
            "White Elo": game["white_elo"],
            "Black Elo": game["black_elo"],
            "Termination": game["termination"],
            "Time Control": game["time_control"],
            "Source File": game["source_file"],
        }
    )

    st.markdown("**Moves**")
    st.code(game["moves_san"] or "No moves found.", language="text")

    st.markdown("**PGN**")
    st.code(game["pgn_text"], language="pgn")
