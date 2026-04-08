# pgn-explorer

Local chess database and Streamlit app for importing, searching, and reviewing PGN game archives.

## Data

Put your personal PGN archive in `pgn/`. The repository ignores personal `.pgn` files by default, but keeps `pgn/example.pgn` so the project remains usable for other people.

## Local setup

Create and activate your virtual environment, then install requirements:

```powershell
python -m venv C:\venvs\pgn-explorer
C:\venvs\pgn-explorer\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

Each import rebuilds `data/games.db` from the PGN file you specify. In other words, rerunning the importer overwrites the current database contents with a fresh import from source.

Import the sample PGN:

```powershell
python import_pgn.py --pgn pgn/example.pgn
```

Import your archive:

```powershell
python import_pgn.py --pgn pgn/all.pgn
```

During import, progress is printed to the terminal.

If you edit or delete games in `pgn/all.pgn`, rerun the importer so the database matches the source again.

Start the app:

```powershell
streamlit run app.py
```

The app currently has two pages:

- `Opening explorer`: explore openings, filter games, and drill into positions move by move
- `Data review`: review games with targeted cleanup queues

## Cleanup workflow

The app is designed around source-first cleanup. If a game is bad, fix or delete it in `pgn/all.pgn`, then rerun the importer.

Useful fields in the app:

- `game_number`: the game's order in the PGN file
- `source_line`: the starting line of the game in `pgn/all.pgn`

The most reliable source reference is `source_line`, because it points directly into the PGN file.

## Data quality checks

The opening explorer shows headline `Data Quality` counts for these checks:

- `Missing result`: games with no result or `*`
- `Missing moves`: games where no move text was imported
- `Not my game`: games where neither White nor Black matches one of your usernames

`My usernames` accepts a comma-separated list and matches case-insensitively. For example:

```text
peletis, Peletis, old_handle
```

The sidebar uses British English in user-facing labels, for example `Colour`.

## Data Review

The `Data review` page currently has these queues:

- `Missing date`: blank dates or `????.??.??`
- `Missing ECO`: games with no ECO code

This page is intended as a review queue rather than an automatic cleanup step.

## Recent Games Ordering

The `Recent games` section on the opening explorer page is ordered by:

1. Date, newest first
2. `game_number`, descending

Partial dates are sorted by their earliest possible concrete date, with less precise dates first when the lower bound is the same. For example:

- `2008.??.??` comes before `2008.01.01`
- `2006.04.??` comes before `2006.04.01`

Fully missing dates sort last.

## Typical cleanup loop

1. Run `streamlit run app.py`
2. Choose a `Data quality` filter
3. Find the bad game and note its `source_line`
4. Edit or delete that game in `pgn/all.pgn`
5. Rerun `python import_pgn.py --pgn pgn/all.pgn`
6. Refresh the app and repeat until the counts are clean

## Scope

Current first version:

- Import PGN games into a local SQLite database
- Search and filter games in Streamlit
- View game metadata, moves, and board replay
