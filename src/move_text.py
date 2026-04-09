from __future__ import annotations

from io import StringIO

import chess.pgn


def parse_move_text(move_text: str) -> tuple[str, ...]:
    cleaned_text = move_text.strip()
    if not cleaned_text:
        return ()

    if cleaned_text.split()[-1] not in {"1-0", "0-1", "1/2-1/2", "*"}:
        cleaned_text = f"{cleaned_text} *"

    game = chess.pgn.read_game(StringIO(f"[Event \"?\"]\n\n{cleaned_text}"))
    if game is None:
        raise ValueError("Could not parse move text.")

    board = game.board()
    san_moves: list[str] = []
    for move in game.mainline_moves():
        san_moves.append(board.san(move))
        board.push(move)

    return tuple(san_moves)
