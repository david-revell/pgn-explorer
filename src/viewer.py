from __future__ import annotations

import streamlit as st


def render_player_summary(counts: dict[str, int]) -> None:
    columns = st.columns(4)
    columns[0].metric("White Games", counts["white_games"])
    columns[1].metric("Black Games", counts["black_games"])
    columns[2].metric("Total Games", counts["total_games"])
    columns[3].metric("W/D/L", f"{counts['wins']}/{counts['draws']}/{counts['losses']}")


def render_quality_summary(counts: dict[str, int]) -> None:
    columns = st.columns(3)
    for column, (label, value) in zip(columns, counts.items()):
        column.metric(label, value)


def render_game_summary(game: dict) -> None:
    st.subheader(f"{game['white']} vs {game['black']}")
    st.caption(
        f"{game['date']} | {game['result']} | ECO {game['eco'] or '?'} | {game['event'] or 'Unknown event'}"
    )

    st.write(
        {
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
