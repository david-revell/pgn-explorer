from __future__ import annotations

from io import StringIO
from pathlib import Path

import chess.pgn


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value == "?":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_pgn_file(pgn_path: Path | str) -> list[dict]:
    path = Path(pgn_path)
    games: list[dict] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
            pgn_text = game.accept(exporter)
            moves = list(game.mainline_moves())
            board = game.board()
            san_moves: list[str] = []
            for move in moves:
                san_moves.append(board.san(move))
                board.push(move)

            headers = game.headers
            games.append(
                {
                    "source_file": path.name,
                    "event": headers.get("Event"),
                    "site": headers.get("Site"),
                    "date": headers.get("Date"),
                    "round": headers.get("Round"),
                    "white": headers.get("White"),
                    "black": headers.get("Black"),
                    "result": headers.get("Result"),
                    "eco": headers.get("ECO"),
                    "white_elo": _parse_int(headers.get("WhiteElo")),
                    "black_elo": _parse_int(headers.get("BlackElo")),
                    "ply_count": _parse_int(headers.get("PlyCount")),
                    "event_date": headers.get("EventDate"),
                    "termination": headers.get("Termination"),
                    "time_control": headers.get("TimeControl"),
                    "moves_san": " ".join(san_moves),
                    "pgn_text": pgn_text,
                }
            )

    return games
