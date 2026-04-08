# Contributing

## Purpose

This project is a local PGN explorer for reviewing, searching, and cleaning a personal chess archive.

## Language

- Use British English in all user-facing text and documentation.
- Prefer British English in new internal names when practical.
- Do not rename existing code purely for style unless already editing that area.

## Data Model

- `game_number` is the meaningful game identifier in the UI.
- `source_line` is the most reliable reference back into the PGN source.
- Do not expose the database row `id` as a primary identifier in the UI unless there is a specific need.

## Workflow

- The PGN file is the source of truth, not the SQLite database.
- If a game is wrong, fix or delete it in the PGN, then rerun the importer.
- Avoid changing user-facing wording or layout without first confirming the intended workflow if the format is important.

## UI Notes

- Keep the home page focused on practical archive statistics and filtering.
- Current player-specific filtering is built around `peletis` unless explicitly changed.
- Prefer simple, readable summaries over dense dashboards.
