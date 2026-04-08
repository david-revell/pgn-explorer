from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re


ECO_PATTERN = re.compile(r"^[A-E][0-9]{2}$")
HEADER_LINE_PATTERN = re.compile(r"^\[(?P<name>[A-Za-z0-9_]+)\s+\"(?P<value>.*)\"\]\s*$")


@dataclass(slots=True)
class PgnGameChunk:
    game_number: int
    start_line: int
    text: str


@dataclass(slots=True)
class PgnSourceSession:
    path: Path
    file_hash: str
    chunks: list[PgnGameChunk]


def validate_eco(eco: str) -> str:
    value = eco.strip().upper()
    if not ECO_PATTERN.fullmatch(value):
        raise ValueError("ECO must use the form A00 to E99.")
    return value


def load_pgn_source_session(pgn_path: Path | str) -> PgnSourceSession:
    path = Path(pgn_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = _split_pgn_chunks(text)
    return PgnSourceSession(
        path=path,
        file_hash=_hash_text(text),
        chunks=chunks,
    )


def save_eco_updates(
    session: PgnSourceSession,
    eco_updates: dict[int, str],
) -> PgnSourceSession:
    current_text = session.path.read_text(encoding="utf-8", errors="replace")
    current_hash = _hash_text(current_text)
    if current_hash != session.file_hash:
        raise RuntimeError("The PGN source changed outside the app. Reload before saving.")

    updated_chunks: list[PgnGameChunk] = []
    for chunk in session.chunks:
        eco_value = eco_updates.get(chunk.game_number)
        if eco_value is None:
            updated_text = chunk.text
        else:
            updated_text = _upsert_eco_tag(chunk.text, validate_eco(eco_value))

        updated_chunks.append(
            PgnGameChunk(
                game_number=chunk.game_number,
                start_line=chunk.start_line,
                text=updated_text,
            )
        )

    updated_text = "\n\n".join(chunk.text.strip() for chunk in updated_chunks if chunk.text.strip()) + "\n"
    session.path.write_text(updated_text, encoding="utf-8", newline="\n")
    return load_pgn_source_session(session.path)


def get_eco_by_game_number(session: PgnSourceSession) -> dict[int, str]:
    eco_by_game_number: dict[int, str] = {}
    for chunk in session.chunks:
        eco_value = _get_header_value(chunk.text, "ECO")
        if eco_value is not None:
            eco_by_game_number[chunk.game_number] = eco_value
    return eco_by_game_number


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _split_pgn_chunks(text: str) -> list[PgnGameChunk]:
    lines = text.splitlines()
    chunks: list[PgnGameChunk] = []
    current_start_line: int | None = None
    current_lines: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("[Event ") and current_lines:
            chunks.append(
                PgnGameChunk(
                    game_number=len(chunks) + 1,
                    start_line=current_start_line or line_number,
                    text="\n".join(current_lines).strip(),
                )
            )
            current_lines = []
            current_start_line = line_number
        elif current_start_line is None and line.strip():
            current_start_line = line_number

        if current_start_line is not None:
            current_lines.append(line)

    if current_lines:
        chunks.append(
            PgnGameChunk(
                game_number=len(chunks) + 1,
                start_line=current_start_line or 1,
                text="\n".join(current_lines).strip(),
            )
        )

    return chunks


def _upsert_eco_tag(game_text: str, eco: str) -> str:
    lines = game_text.splitlines()
    header_end_index = _find_header_end_index(lines)
    header_lines = lines[:header_end_index]
    body_lines = lines[header_end_index:]
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]

    eco_updated = False
    output_headers: list[str] = []
    for line in header_lines:
        match = HEADER_LINE_PATTERN.match(line.strip())
        if match and match.group("name") == "ECO":
            output_headers.append(f'[ECO "{eco}"]')
            eco_updated = True
        else:
            output_headers.append(line)

    if not eco_updated:
        insert_index = _find_eco_insert_index(output_headers)
        output_headers.insert(insert_index, f'[ECO "{eco}"]')

    parts = ["\n".join(output_headers)]
    if body_lines:
        parts.append("\n".join(body_lines))
    return "\n\n".join(part.rstrip() for part in parts if part is not None).strip()


def _get_header_value(game_text: str, tag_name: str) -> str | None:
    header_end_index = _find_header_end_index(game_text.splitlines())
    for line in game_text.splitlines()[:header_end_index]:
        match = HEADER_LINE_PATTERN.match(line.strip())
        if match and match.group("name") == tag_name:
            return match.group("value")
    return None


def _find_header_end_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if not line.strip():
            return index
    return len(lines)


def _find_eco_insert_index(header_lines: list[str]) -> int:
    preferred_after = ("Opening", "Variation")
    last_match_index = -1
    for index, line in enumerate(header_lines):
        match = HEADER_LINE_PATTERN.match(line.strip())
        if match and match.group("name") in preferred_after:
            last_match_index = index

    if last_match_index >= 0:
        return last_match_index + 1
    return len(header_lines)
