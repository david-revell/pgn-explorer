from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def _render_summary_table(table_df: pd.DataFrame) -> None:
    st.dataframe(table_df, use_container_width=True, hide_index=True)


def render_quality_summary(counts: dict[str, int]) -> None:
    columns = st.columns(3)
    for column, (label, value) in zip(columns, counts.items()):
        colour = "#2e7d32" if value == 0 else "#c62828"
        column.markdown(
            (
                f"{label}: "
                f"<span style='color:{colour}; font-size: 1.8rem; font-weight: 700;'>{value:,}</span>"
            ),
            unsafe_allow_html=True,
        )


def _format_results_table(table_df: pd.DataFrame, first_column: str) -> pd.DataFrame:
    formatted_df = table_df.rename(
        columns={
            "games": "Games",
            "white": "White",
            "draw": "Draw",
            "black": "Black",
        }
    ).copy()

    games = formatted_df["Games"]
    formatted_df["Games"] = games.map(lambda value: f"{value:,}")
    formatted_df["White"] = (formatted_df["White"] / games * 100).fillna(0).map(_format_percent)
    formatted_df["Draw"] = (formatted_df["Draw"] / games * 100).fillna(0).map(_format_percent)
    formatted_df["Black"] = (formatted_df["Black"] / games * 100).fillna(0).map(_format_percent)

    leading_columns = [
        column
        for column in formatted_df.columns
        if column not in {"Games", "White", "Draw", "Black"}
    ]
    column_order = leading_columns + ["Games", "White", "Draw", "Black"]
    return formatted_df[column_order]


def render_player_summary(summary_df: pd.DataFrame) -> None:
    formatted_df = _format_results_table(summary_df, "Colour")
    column_order = ["Colour", "Position", "Games", "White", "Draw", "Black"]
    _render_summary_table(formatted_df[column_order])


def render_move_summary(moves_df: pd.DataFrame) -> None:
    if moves_df.empty:
        _render_summary_table(pd.DataFrame(columns=["Move", "Games", "White", "Draw", "Black"]))
        return

    move_df = moves_df.rename(columns={"move": "Move"}).copy()
    move_df["Move"] = move_df["Move"].map(lambda move: f"1. {move}")
    _render_summary_table(_format_results_table(move_df, "Move"))


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
