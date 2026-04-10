from __future__ import annotations

from io import StringIO
from pathlib import Path
from time import perf_counter

from collections.abc import Callable

import chess.pgn

from src.positions import build_position_key


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


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


def _date_sort_fields(value: str | None) -> tuple[int, int]:
    cleaned = (value or "").strip()
    if not cleaned or cleaned == "????.??.??":
        return (0, 99)

    year = cleaned[0:4]
    month = cleaned[5:7]
    day = cleaned[8:10]

    safe_year = year if year.isdigit() else "0000"
    safe_month = "01" if month == "??" else month
    safe_day = "01" if day == "??" else day

    if month == "??":
        precision = 1
    elif day == "??":
        precision = 2
    else:
        precision = 3

    try:
        return (int(f"{safe_year}{safe_month}{safe_day}"), precision)
    except ValueError:
        return (0, 99)


def parse_pgn_file(
    pgn_path: Path | str,
    progress_every: int = 500,
    progress_callback: Callable[[int, int | None, float], None] | None = None,
) -> list[dict]:
    return [
        game_row
        for game_row, _ in iter_parsed_games(
            pgn_path,
            progress_every=progress_every,
            progress_callback=progress_callback,
        )
    ]


def iter_parsed_games(
    pgn_path: Path | str,
    progress_every: int = 500,
    progress_callback: Callable[[int, int | None, float], None] | None = None,
) -> tuple[dict, list[dict]]:
    path = Path(pgn_path)
    total_games = count_games_in_pgn(path)
    started = perf_counter()

    for game_number, (source_line, game_text) in enumerate(_iter_game_chunks(path), start=1):
        game = chess.pgn.read_game(StringIO(game_text))
        if game is None:
            continue

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        pgn_text = game.accept(exporter)
        board = game.board()
        san_moves: list[str] = []
        position_rows: list[dict[str, int | str | None]] = []
        ply = 0
        for move in game.mainline_moves():
            san_move = board.san(move)
            position_rows.append(
                {
                    "ply": ply,
                    "position_key": build_position_key(board),
                    "next_move": san_move,
                }
            )
            san_moves.append(san_move)
            board.push(move)
            ply += 1
        position_rows.append(
            {
                "ply": ply,
                "position_key": build_position_key(board),
                "next_move": None,
            }
        )

        headers = game.headers
        date_sort_key, date_precision = _date_sort_fields(headers.get("Date"))
        yield (
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
                "white_norm": _normalize_text(headers.get("White")),
                "black_norm": _normalize_text(headers.get("Black")),
                "date_sort_key": date_sort_key,
                "date_precision": date_precision,
                "moves_san": " ".join(san_moves),
                "pgn_text": pgn_text,
            },
            position_rows,
        )

        if progress_callback is not None and (
            game_number == 1
            or game_number % progress_every == 0
            or game_number == total_games
        ):
            progress_callback(game_number, total_games, perf_counter() - started)
