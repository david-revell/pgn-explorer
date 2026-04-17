# pgn-explorer

Local chess database and Streamlit app for importing, searching, and reviewing PGN game archives.

**Public app:** https://pgn-explorer.streamlit.app

> **Desktop or large tablet only.** The app is not optimised for small screens. Streamlit's column layout does not reflow on narrow viewports, and the board is rendered at a fixed size — both combine to make the experience poor on a phone or tablet in portrait mode. Use a desktop browser or a large tablet in landscape.

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

## Public-safe dataset

If you want a deployable public version without exposing your full private PGN
archive, generate an anonymised PGN copy first:

```powershell
python anonymize_pgn.py --input pgn/all.pgn --output pgn/public_anonymised.pgn
```

The anonymiser is intentionally simple:

- online platform identities such as `Lichess`, `Chess.com`, `GameKnot`, and
  `GameColony` are normalised and preserved
- real-world `Site` and `Event` values are collapsed to `Over-the-board`
- safe public handles can remain
- other player identities are replaced with stable aliases such as
  `Player_0001`

## Local setup

Create and activate your virtual environment, then install requirements:

```powershell
python -m venv C:\venvs\pgn-explorer
C:\venvs\pgn-explorer\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

Each import rebuilds the target SQLite database from the PGN file you specify.
In other words, rerunning the importer overwrites the current database contents
with a fresh import from source.

The target database is determined by `PGN_EXPLORER_MODE` (or `PGN_EXPLORER_DB_PATH`).
Without setting either, imports go to `data/games.db` (private mode default).

Import the sample PGN → `data/games.db`:

```powershell
python import_pgn.py --pgn pgn/example.pgn
```

Import your archive → `data/games.db`:

```powershell
python import_pgn.py --pgn pgn/all.pgn
```

Import in public mode → `data/public_games.db`:

```powershell
$env:PGN_EXPLORER_MODE="public"
python import_pgn.py
```

During import, progress is printed to the terminal.

If you edit games in `pgn/all.pgn`, rerun the importer so the database matches the source again. Games can also be deleted directly in the app from the `Data review` page — that updates both the PGN and the database in one step with no rebuild required.

Start the app:

```powershell
streamlit run app.py
```

Start the app in public mode:

```powershell
$env:PGN_EXPLORER_MODE="public"
streamlit run app.py
```

For a Streamlit Community Cloud deployment, point the app at
`streamlit_app.py`. That wrapper forces:

- `PGN_EXPLORER_MODE=public`
- `PGN_EXPLORER_PGN_PATH=pgn/public_anonymised.pgn` via mode defaults
- `PGN_EXPLORER_DB_PATH=data/public_games.db` via mode defaults
- `PGN_EXPLORER_ALLOW_PGN_WRITES=0`

Build `data/public_games.db` locally first:

```powershell
$env:PGN_EXPLORER_MODE="public"
python import_pgn.py
```

Then commit `pgn/public_anonymised.pgn`, `data/public_games.db`, and
`streamlit_app.py`, and deploy that file on Community Cloud. In that deployed
mode, the app is intentionally read-only: PGN write-back and in-app database
rebuild are both disabled.

Local-only Windows launchers can also be kept at repo root:

- `run_private.bat`
- `run_public.bat`

These are intentionally ignored by git.

The app currently has two pages:

- `Opening explorer`: explore openings, filter games, drill into positions move by move, and seed exploration from a direct FEN
- `Data review`: review games with targeted cleanup queues, with in-app deletion and batch ECO editing

The `Opening explorer` currently includes:

- a dynamic page title reflecting the active filters (e.g. `Games of peletis as White — Ruy Lopez`)
- a board for the current position
- an opening label showing `ECO + name`, with the reference opening PGN line directly underneath
- a narrow control strip with rotate, back, and reset actions
- a position-based move breakdown panel beside the board
- a position-based matching-games list under the board row
- clicking a row in the matching-games list loads that game on a board with `<<` `<` `>` `>>` navigation and left/right arrow key support
- an editable move text input under the board row, so the current line can be typed and resubmitted directly
- an optional sidebar FEN seed, so exploration can start from any directly entered position

## Filters

The sidebar exposes filters that apply across the opening explorer and game list.

### Player filter

The player field defaults to `peletis` on load. Clear it to browse all games regardless of player.

Matches are case-insensitive. By default the search is exact — typing `Magnus` will match a player named `Magnus` but not `Magnus Carlsen`.

The colour filter refers to the typed player — selecting `White` shows games where that player was White.

Use `%` as a wildcard to match any characters:

| Input | Matches |
|---|---|
| `Magnus` | Exactly "Magnus" (any case) |
| `Magnus%` | Any name starting with "Magnus" |
| `%son` | Any name ending in "son" |
| `%agn%` | Any name containing "agn" |

### Player aliases

If a player appears under multiple names (e.g. a real name and an online handle), aliases can be defined in `src/aliases.py`. When a search term matches a known alias group, all variants are searched automatically and an info banner lists the expanded aliases.

### Opening filter

A single input handles both ECO codes and opening names. The input is interpreted by shape:

- **ECO code** — a letter A–E optionally followed by up to two digits (e.g. `C`, `C6`, `C65`). Treated as a prefix match against the game's ECO tag.
- **Opening name** — anything else. Treated as a case-insensitive substring match against the precomputed final opening name (e.g. `frenc` matches "French Defence" and all its variations).

The final opening name is the last position in the game that was recognised against the opening reference dataset — i.e. the deepest named position before the game went out of book. It is precomputed during import and stored on the `games` table, so filtering is fast.

If the opening reference data is re-imported separately (`internal/import_openings.py`), final opening names are refreshed automatically.

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

The app supports two cleanup paths:

**In-app deletion** (from the `Data review` page): select one or more games using the checkboxes, then confirm deletion. The app removes the games from both the PGN source and the database in one step — no rebuild required. `game_number` and `source_line` are recalculated automatically.

**Manual PGN edit**: find the game using the `source_line` field (the starting line in the PGN file), edit it directly in `pgn/all.pgn`, then rerun the importer. Use this for corrections (e.g. fixing a date or result) rather than deletions.

Useful fields in the app:

- `game_number`: the game's sequential position in the PGN file
- `source_line`: the starting line of the game in `pgn/all.pgn`

## Data quality checks

The `Data review` page includes a `Critical issues` section with these checks:

- `Missing result`: games with no result or `*`
- `Missing moves`: games where no move text was imported
- `Not my game`: games where neither White nor Black matches one of your usernames

The current app treats `peletis` as the internal player identity for player-specific filtering and summaries.

The sidebar uses British English in user-facing labels, for example `Colour`.

## Data Review

The `Data review` page currently has these queues (shown alphabetically, defaulting to `Short games`):

- `Duplicate games`: games with identical players, date, and move sequence — grouped in pairs so duplicates appear side by side. The `site` column helps confirm whether two entries are genuinely the same game.
- `Missing date`: blank dates or `????.??.??`
- `Missing ECO`: games with no ECO code
- `Short games`: games at or below a configurable ply threshold (default 3), adjustable via a sidebar input

Clicking a row in any queue loads that game on a board with full move navigation.

In any queue, one or more rows can be selected using the checkboxes and deleted directly — this removes the games from both the PGN source and the database and recalculates `game_number` and `source_line` for surviving games. A confirmation step is shown before any deletion is performed. Deletion is disabled in public/read-only mode.

For `Missing ECO`, the app includes a batch editor:

- stage ECO values for many games in Streamlit
- save those ECO tags back to the active PGN source
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
3. For missing ECOs, stage one or more ECO edits in the batch editor and save them to the active PGN source, then rebuild the database
4. To delete duplicate or short games, select them with the row checkboxes and confirm — the PGN and database are updated immediately, no rebuild needed
5. For other fixes (e.g. correcting a date or result), note the `source_line`, edit the game directly in the PGN source, then rerun the importer
6. Repeat until the counts are clean

## Limitations

These were considered or tried and decided against:

- **Interactive piece movement** — dragging or clicking pieces on the board to make moves requires a custom JavaScript/React component. Streamlit's board rendering is a static SVG with no bidirectional communication, so this would be a significant build rather than a configuration change.
- **Mobile-friendly layout** — Streamlit's column layout does not reflow on narrow viewports, and the board renders at a fixed size. The app works well on desktop and large tablets in landscape; phones and portrait tablets are not supported.
- **Move list with click-to-position** — a scrollable move list beside the board with clickable moves was implemented but reverted. Streamlit renders one button per move, which for a typical 60-move game means ~120 widgets and makes the page noticeably slow.

## Scope

- Import PGN games into a local SQLite database
- Search and filter games in Streamlit
- Explore openings position by position on a board, with transposition awareness and opening labels
- Click any game in a list to load it on a board and step through the moves
- Detect duplicate games and short games via dedicated review queues
- Delete games in-app from any review queue — updates the PGN source and database atomically, with automatic renumbering
- Edit missing ECO tags in batches and write them back to the active PGN source when writes are enabled
