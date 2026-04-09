from __future__ import annotations

from io import StringIO

import chess
import chess.pgn
import chess.svg
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


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


def _inject_breakdown_styles() -> None:
    st.markdown(
        """
        <style>
        .breakdown-header {
            font-size: 0.95rem;
            font-weight: 600;
            color: #38463a;
            margin-bottom: 0.2rem;
        }
        .breakdown-header--right {
            text-align: right;
        }
        .breakdown-text {
            font-size: 0.98rem;
            padding-top: 0.18rem;
            white-space: nowrap;
        }
        .breakdown-games {
            font-size: 0.98rem;
            padding-top: 0.18rem;
            text-align: right;
            white-space: nowrap;
        }
        .result-bar {
            position: relative;
            display: flex;
            height: 1.6rem;
            border-radius: 0.8rem;
            overflow: hidden;
            background: #e6e6e6;
            border: 1px solid #c9c9c9;
        }
        .result-bar__white {
            background: linear-gradient(180deg, #f7f7f7 0%, #ececec 100%);
            color: #505050;
        }
        .result-bar__draw {
            background: linear-gradient(180deg, #d3d3d3 0%, #bdbdbd 100%);
        }
        .result-bar__black {
            background: linear-gradient(180deg, #7b7b7b 0%, #4f4f4f 100%);
            color: #ffffff;
        }
        .result-bar__segment {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.95rem;
            line-height: 1;
            min-width: 0;
        }
        .result-bar__label {
            font-weight: 600;
            white-space: nowrap;
        }
        .breakdown-row {
            margin-bottom: 0.32rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_result_bar(white: int, draw: int, black: int) -> str:
    games = white + draw + black
    white_pct = (white / games * 100) if games else 0
    draw_pct = (draw / games * 100) if games else 0
    black_pct = (black / games * 100) if games else 0

    white_label = _format_percent(white_pct) if white_pct >= 12 else ""
    draw_label = _format_percent(draw_pct) if draw_pct >= 12 else ""
    black_label = _format_percent(black_pct) if black_pct >= 12 else ""

    return (
        "<div class='result-bar'>"
        f"<div class='result-bar__segment result-bar__white' style='width:{white_pct:.3f}%'>"
        f"<span class='result-bar__label'>{white_label}</span>"
        "</div>"
        f"<div class='result-bar__segment result-bar__draw' style='width:{draw_pct:.3f}%'>"
        f"<span class='result-bar__label'>{draw_label}</span>"
        "</div>"
        f"<div class='result-bar__segment result-bar__black' style='width:{black_pct:.3f}%'>"
        f"<span class='result-bar__label'>{black_label}</span>"
        "</div>"
        "</div>"
    )


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
    _inject_breakdown_styles()
    headers = st.columns([0.8, 0.9, 5.3])
    headers[0].markdown("<div class='breakdown-header'>Colour</div>", unsafe_allow_html=True)
    headers[1].markdown("<div class='breakdown-header breakdown-header--right'>Games</div>", unsafe_allow_html=True)
    headers[2].markdown("<div class='breakdown-header'>White / Draw / Black</div>", unsafe_allow_html=True)

    for row in summary_df.itertuples(index=False):
        columns = st.columns([0.8, 0.9, 5.3])
        columns[0].markdown(f"<div class='breakdown-text'>{row.Colour}</div>", unsafe_allow_html=True)
        columns[1].markdown(f"<div class='breakdown-games'>{int(row.games):,}</div>", unsafe_allow_html=True)
        columns[2].markdown(_render_result_bar(int(row.white), int(row.draw), int(row.black)), unsafe_allow_html=True)


def render_move_summary(moves_df: pd.DataFrame) -> None:
    if moves_df.empty:
        _inject_breakdown_styles()
        headers = st.columns([0.9, 0.9, 5.2])
        headers[0].markdown("<div class='breakdown-header'>Move</div>", unsafe_allow_html=True)
        headers[1].markdown("<div class='breakdown-header breakdown-header--right'>Games</div>", unsafe_allow_html=True)
        headers[2].markdown("<div class='breakdown-header'>White / Draw / Black</div>", unsafe_allow_html=True)
        return

    _inject_breakdown_styles()
    headers = st.columns([0.9, 0.9, 5.2])
    headers[0].markdown("<div class='breakdown-header'>Move</div>", unsafe_allow_html=True)
    headers[1].markdown("<div class='breakdown-header breakdown-header--right'>Games</div>", unsafe_allow_html=True)
    headers[2].markdown("<div class='breakdown-header'>White / Draw / Black</div>", unsafe_allow_html=True)

    for row in moves_df.itertuples(index=False):
        columns = st.columns([0.9, 0.9, 5.2])
        columns[0].markdown(f"<div class='breakdown-text'>{row.move}</div>", unsafe_allow_html=True)
        columns[1].markdown(f"<div class='breakdown-games'>{int(row.games):,}</div>", unsafe_allow_html=True)
        columns[2].markdown(_render_result_bar(int(row.white), int(row.draw), int(row.black)), unsafe_allow_html=True)


def render_clickable_move_summary(
    moves_df: pd.DataFrame,
    ply_index: int,
    key_prefix: str,
) -> str | None:
    if moves_df.empty:
        render_move_summary(moves_df)
        return None

    _inject_breakdown_styles()
    headers = st.columns([0.9, 0.9, 5.2])
    headers[0].markdown("<div class='breakdown-header'>Move</div>", unsafe_allow_html=True)
    headers[1].markdown("<div class='breakdown-header breakdown-header--right'>Games</div>", unsafe_allow_html=True)
    headers[2].markdown("<div class='breakdown-header'>White / Draw / Black</div>", unsafe_allow_html=True)

    for row in moves_df.itertuples(index=False):
        columns = st.columns([0.9, 0.9, 5.2])
        move_label = format_move_label(row.move, ply_index)
        if columns[0].button(move_label, key=f"{key_prefix}_{row.move}"):
            return str(row.move)

        columns[1].markdown(f"<div class='breakdown-games'>{int(row.games):,}</div>", unsafe_allow_html=True)
        columns[2].markdown(_render_result_bar(int(row.white), int(row.draw), int(row.black)), unsafe_allow_html=True)

    return None


@st.cache_data(show_spinner=False)
def _load_game_replay_data(pgn_text: str) -> dict[str, object]:
    game = chess.pgn.read_game(StringIO(pgn_text))
    if game is None:
        return {"san_moves": [], "uci_moves": []}

    board = game.board()
    san_moves: list[str] = []
    uci_moves: list[str] = []
    for move in game.mainline_moves():
        san_moves.append(board.san(move))
        uci_moves.append(move.uci())
        board.push(move)

    return {
        "san_moves": san_moves,
        "uci_moves": uci_moves,
    }


def _build_board_position(uci_moves: list[str], ply_index: int) -> tuple[chess.Board, chess.Move | None]:
    board = chess.Board()
    last_move: chess.Move | None = None
    for move_uci in uci_moves[:ply_index]:
        last_move = chess.Move.from_uci(move_uci)
        board.push(last_move)
    return board, last_move


def build_board_from_san_sequence(move_sequence: tuple[str, ...]) -> tuple[chess.Board, chess.Move | None]:
    board = chess.Board()
    last_move: chess.Move | None = None
    for san_move in move_sequence:
        last_move = board.parse_san(san_move)
        board.push(last_move)
    return board, last_move


def render_board(board: chess.Board, last_move: chess.Move | None = None, size: int = 440) -> None:
    orientation = chess.WHITE if st.session_state.get("board_orientation", "White") == "White" else chess.BLACK
    board_svg = chess.svg.board(board=board, lastmove=last_move, size=size, orientation=orientation)
    components.html(board_svg, height=size + 20)


def _format_replay_status(ply_index: int, total_plies: int) -> str:
    if ply_index <= 0:
        return f"Start position | 0/{total_plies} plies"

    move_number = (ply_index + 1) // 2
    side = "White" if ply_index % 2 == 1 else "Black"
    return f"After {move_number}. {side} | {ply_index}/{total_plies} plies"


def _render_move_list(san_moves: list[str], current_ply: int) -> None:
    if not san_moves:
        st.caption("No moves found.")
        return

    tokens: list[str] = []
    for index, san_move in enumerate(san_moves):
        move_number = index // 2 + 1
        if index % 2 == 0:
            token = f"{move_number}. {san_move}"
        else:
            token = san_move

        if index + 1 == current_ply:
            tokens.append(f"**[{token}]**")
        else:
            tokens.append(token)

    st.markdown(" ".join(tokens))


def render_game_summary(game: dict) -> None:
    st.subheader(f"{game['white']} vs {game['black']}")
    st.caption(
        f"{game['date']} | {game['result']} | ECO {game['eco'] or '?'} | {game['event'] or 'Unknown event'}"
    )

    replay_data = _load_game_replay_data(game["pgn_text"])
    san_moves = [str(move) for move in replay_data["san_moves"]]
    uci_moves = [str(move) for move in replay_data["uci_moves"]]
    total_plies = len(uci_moves)
    viewer_key = f"game_viewer_{game['id']}"
    ply_key = f"{viewer_key}_ply"

    if ply_key not in st.session_state or st.session_state[ply_key] > total_plies:
        st.session_state[ply_key] = 0

    current_ply = int(st.session_state[ply_key])

    st.markdown("**Board**")
    control_columns = st.columns([1, 1, 1, 1, 5])
    if control_columns[0].button("Start", key=f"{viewer_key}_start"):
        st.session_state[ply_key] = 0
        st.rerun()
    if control_columns[1].button("Back", key=f"{viewer_key}_back", disabled=current_ply <= 0):
        st.session_state[ply_key] = current_ply - 1
        st.rerun()
    if control_columns[2].button("Next", key=f"{viewer_key}_next", disabled=current_ply >= total_plies):
        st.session_state[ply_key] = current_ply + 1
        st.rerun()
    if control_columns[3].button("End", key=f"{viewer_key}_end", disabled=current_ply >= total_plies):
        st.session_state[ply_key] = total_plies
        st.rerun()
    control_columns[4].caption(_format_replay_status(current_ply, total_plies))

    slider_value = st.slider(
        "Ply",
        min_value=0,
        max_value=total_plies,
        value=current_ply,
        key=f"{viewer_key}_slider",
    )
    if slider_value != current_ply:
        st.session_state[ply_key] = slider_value
        current_ply = slider_value

    board, last_move = _build_board_position(uci_moves, current_ply)
    render_board(board, last_move=last_move, size=440)

    st.markdown("**Moves**")
    _render_move_list(san_moves, current_ply)

    st.markdown("**PGN**")
    st.code(game["pgn_text"], language="pgn")
