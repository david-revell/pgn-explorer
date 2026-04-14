# pgn-explorer

Local chess database and Streamlit app for importing, searching, and reviewing PGN game archives.

## Data

Put your personal PGN archive in `pgn/`. The repository ignores personal `.pgn` files by default, but keeps `pgn/example.pgn` so the project remains usable for other people.

The app can also run in different data modes via environment variables:

- `PGN_EXPLORER_MODE=private` (default)
- `PGN_EXPLORER_MODE=public`
- optional overrides:
  - `PGN_EXPLORER_PGN_PATH`
  - `PGN_EXPLORER_DB_PATH`
  - `PGN_EXPLORER_ALLOW_PGN_WRITES`

Default paths by mode:

- `private`
  - `pgn/all.pgn`
  - `data/games.db`
  - PGN writes enabled
- `public`
  - `pgn/public_anonymised.pgn`
  - `data/public_games.db`
  - PGN writes disabled

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

- `Opening explorer`: explore openings, filter games, drill into positions move by move, and seed exploration from a direct FEN
- `Data review`: review games with targeted cleanup queues

The `Opening explorer` currently includes:

- a board for the current position
- an opening label showing `ECO + name`, with the reference opening PGN line directly underneath
- a narrow control strip with rotate, back, and reset actions
- a position-based move breakdown panel beside the board
- a position-based matching-games list under the board row
- an editable move text input under the board row, so the current line can be typed and resubmitted directly
- an optional sidebar FEN seed, so exploration can start from any directly entered position

## Position-based explorer

The opening explorer now runs on precomputed position data rather than only a literal move prefix.

- each imported game stores one normalized position key per ply in a dedicated `positions` table
- the key includes piece placement, side to move, castling rights, and only legally relevant en passant state
- the move breakdown and matching-games sections both query by position, so the explorer is transposition-aware
- opening reference data is imported separately into `opening_positions`, allowing the current position to resolve to an opening name by position instead of by ECO alone
- opening lookup falls back to the most recent named position in the current explored line, so the label persists after unnamed continuation moves

## Opening reference data

Opening-name lookup is built from the Lichess opening dataset:

- repository: `https://github.com/lichess-org/chess-openings`
- source files: `a.tsv` to `e.tsv`

Those source TSVs contain `eco`, `name`, and `pgn`. This project then:

1. Parses each PGN line
2. Computes the final opening position as a simplified FEN-style key
3. Stores that key in the `opening_positions` table in `data/games.db`

This lets the app identify openings by position, which is important for transpositions.

Local commands:

```powershell
python internal\build_openings_tsv.py --output internal\openings.tsv
python internal\import_openings.py --input internal\openings.tsv
```

## Cleanup workflow

The app is designed around source-first cleanup. If a game is bad, fix or delete it in `pgn/all.pgn`, then rerun the importer.

Useful fields in the app:

- `game_number`: the game's order in the PGN file
- `source_line`: the starting line of the game in `pgn/all.pgn`

The most reliable source reference is `source_line`, because it points directly into the PGN file.

## Data quality checks

The `Data review` page includes a `Critical issues` section with these checks:

- `Missing result`: games with no result or `*`
- `Missing moves`: games where no move text was imported
- `Not my game`: games where neither White nor Black matches one of your usernames

The current app treats `peletis` as the internal player identity for player-specific filtering and summaries.

The sidebar uses British English in user-facing labels, for example `Colour`.

## Data Review

The `Data review` page currently has these queues:

- `Missing date`: blank dates or `????.??.??`
- `Missing ECO`: games with no ECO code

This page is intended as a review queue rather than an automatic cleanup step.

For `Missing ECO`, the app now includes a batch editor:

- stage ECO values for many games in Streamlit
- save those ECO tags back to `pgn/all.pgn`
- rebuild the database separately when you are ready

This avoids a full rebuild after every single ECO change. Until you rebuild, the database-backed queue will still show the older ECO state.

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
2. Open `Data review`
3. For missing ECOs, stage one or more ECO edits in the batch editor and save them to `pgn/all.pgn`
4. For other fixes, find the bad game and note its `source_line`
5. Edit or delete that game in `pgn/all.pgn`
6. Rerun `python import_pgn.py --pgn pgn/all.pgn`
7. Refresh the app and repeat until the counts are clean

## Scope

Current first version:

- Import PGN games into a local SQLite database
- Search and filter games in Streamlit
- View the current opening position on a board while exploring moves
- Edit missing ECO tags in batches and write them back to `pgn/all.pgn`
- View the selected game's PGN directly
