from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from src.db import DEFAULT_DB_PATH, get_connection, replace_games
from src.parser import parse_pgn_file


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


def main() -> None:
    args = parse_args()
    if not args.pgn.exists():
        raise SystemExit(f"PGN file not found: {args.pgn}")

    started = perf_counter()
    print(f"Reading games from {args.pgn} ...")
    print("The import rebuilds the database from this PGN file.")
    games = parse_pgn_file(args.pgn, progress_callback=report_progress)
    print(f"Parsed {len(games)} games in {perf_counter() - started:.1f}s.")

    with get_connection(args.db) as connection:
        print(f"Writing {len(games)} games to {args.db} ...")
        replace_games(connection, games)

    print(f"Wrote database to {args.db} in {perf_counter() - started:.1f}s.")


if __name__ == "__main__":
    main()
