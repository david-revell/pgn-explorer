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

## Scope

Current first version:

- Import PGN games into a local SQLite database
- Search and filter games in Streamlit
- View game metadata, moves, and board replay
