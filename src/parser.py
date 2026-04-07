from __future__ import annotations

from io import StringIO
from pathlib import Path
from time import perf_counter

from collections.abc import Callable

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


def _iter_game_chunks(pgn_path: Path) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    current_start_line: int | None = None
    current_lines: list[str] = []

    with pgn_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.startswith("[Event ") and current_lines:
                chunks.append((current_start_line or line_number, "".join(current_lines).strip()))
                current_lines = []
                current_start_line = line_number
            elif current_start_line is None and line.strip():
                current_start_line = line_number

            if current_start_line is not None:
                current_lines.append(line)

    if current_lines:
        chunks.append((current_start_line or 1, "".join(current_lines).strip()))

    return chunks


def count_games_in_pgn(pgn_path: Path | str) -> int:
    path = Path(pgn_path)
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("[Event "):
                count += 1
    return count


def parse_pgn_file(
    pgn_path: Path | str,
    progress_every: int = 500,
    progress_callback: Callable[[int, int | None, float], None] | None = None,
) -> list[dict]:
    path = Path(pgn_path)
    games: list[dict] = []
    total_games = count_games_in_pgn(path)
    started = perf_counter()

    for game_number, (source_line, game_text) in enumerate(_iter_game_chunks(path), start=1):
        game = chess.pgn.read_game(StringIO(game_text))
        if game is None:
            continue

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
                "game_number": game_number,
                "source_line": source_line,
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

        if progress_callback is not None and (
            game_number == 1
            or game_number % progress_every == 0
            or game_number == total_games
        ):
            progress_callback(game_number, total_games, perf_counter() - started)

    return games
