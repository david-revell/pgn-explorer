from __future__ import annotations

import chess


def build_position_key(board: chess.Board) -> str:
    castling = board.castling_xfen() or "-"
    en_passant = "-"
    if board.ep_square is not None and board.has_legal_en_passant():
        en_passant = chess.square_name(board.ep_square)

    turn = "w" if board.turn == chess.WHITE else "b"
    return f"{board.board_fen()} {turn} {castling} {en_passant}"


def normalize_fen(fen: str) -> str:
    return build_position_key(chess.Board(fen))
