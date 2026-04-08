from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def format_move_label(move: str, ply_index: int) -> str:
    move_number = ply_index // 2 + 1
    if ply_index % 2 == 0:
        return f"{move_number}. {move}"
    return f"{move_number}... {move}"


def format_position_label(move_sequence: tuple[str, ...]) -> str:
    if not move_sequence:
        return "Start"

    parts: list[str] = []
    for index, move in enumerate(move_sequence):
        move_number = index // 2 + 1
        if index % 2 == 0:
            parts.append(f"{move_number}. {move}")
        else:
            parts.append(move)
    return " ".join(parts)


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
    column_order = ["Colour", "Games", "White", "Draw", "Black"]
    _render_summary_table(formatted_df[column_order])


def render_move_summary(moves_df: pd.DataFrame) -> None:
    if moves_df.empty:
        _render_summary_table(pd.DataFrame(columns=["Move", "Games", "White", "Draw", "Black"]))
        return

    move_df = moves_df.rename(columns={"move": "Move"}).copy()
    _render_summary_table(_format_results_table(move_df, "Move"))


def render_clickable_move_summary(
    moves_df: pd.DataFrame,
    ply_index: int,
    key_prefix: str,
) -> str | None:
    if moves_df.empty:
        render_move_summary(moves_df)
        return None

    headers = st.columns([2, 1, 1, 1, 1])
    for column, label in zip(headers, ["Move", "Games", "White", "Draw", "Black"]):
        column.markdown(f"**{label}**")

    for row in moves_df.itertuples(index=False):
        columns = st.columns([2, 1, 1, 1, 1])
        move_label = format_move_label(row.move, ply_index)
        if columns[0].button(move_label, key=f"{key_prefix}_{row.move}"):
            return str(row.move)

        games = int(row.games)
        white_pct = _format_percent((row.white / games * 100) if games else 0)
        draw_pct = _format_percent((row.draw / games * 100) if games else 0)
        black_pct = _format_percent((row.black / games * 100) if games else 0)

        columns[1].markdown(f"{games:,}")
        columns[2].markdown(white_pct)
        columns[3].markdown(draw_pct)
        columns[4].markdown(black_pct)

    return None


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
