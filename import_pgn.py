from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from src.db import DEFAULT_DB_PATH, get_connection, replace_games
from src.parser import count_games_in_pgn, iter_parsed_games


DEFAULT_PGN_PATH = Path("pgn/all.pgn")


def report_progress(parsed_games: int, total_games: int | None, elapsed_seconds: float) -> None:
    if total_games:
        print(f"Parsed {parsed_games}/{total_games} games in {elapsed_seconds:.1f}s...")
    else:
        print(f"Parsed {parsed_games} games in {elapsed_seconds:.1f}s...")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a PGN archive into SQLite.")
    parser.add_argument(
        "--pgn",
        type=Path,
        default=DEFAULT_PGN_PATH,
        help="Path to the PGN file to import.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file to write.",
    )
    return parser.parse_args()


def import_archive(
    pgn_path: Path,
    db_path: Path,
    progress_callback: Callable[[int, int | None, float], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> int:
    started = perf_counter()
    print(f"Reading games from {pgn_path} ...")
    print("The import rebuilds the database from this PGN file.")
    total_games = count_games_in_pgn(pgn_path)

    def handle_progress(parsed_games: int, total_games: int | None, elapsed_seconds: float) -> None:
        report_progress(parsed_games, total_games, elapsed_seconds)
        if progress_callback is not None:
            progress_callback(parsed_games, total_games, elapsed_seconds)

    if status_callback is not None:
        status_callback("Parsing PGN...")

    with get_connection(db_path) as connection:
        parsed_games = iter_parsed_games(pgn_path, progress_callback=handle_progress)
        if status_callback is not None:
            status_callback(f"Writing {total_games} games to the database...")
        print(f"Writing {total_games} games to {db_path} ...")
        imported_games, imported_positions = replace_games(connection, parsed_games)

    if status_callback is not None:
        status_callback(
            f"Finished rebuild with {imported_games} games and {imported_positions} stored positions."
        )
    print(f"Wrote {imported_games} games and {imported_positions} positions to {db_path} in {perf_counter() - started:.1f}s.")
    return imported_games


def main() -> None:
    args = parse_args()
    if not args.pgn.exists():
        raise SystemExit(f"PGN file not found: {args.pgn}")

    import_archive(args.pgn, args.db)


if __name__ == "__main__":
    main()
