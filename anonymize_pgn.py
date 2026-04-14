from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


HEADER_LINE_PATTERN = re.compile(r'^\[(?P<name>[A-Za-z0-9_]+)\s+"(?P<value>.*)"\]\s*$')

SAFE_PLAYER_NAMES = {
    "peletis",
    "oldjingleballicks",
    "oldjingleballiks",
}

CHESS_CLUB_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bbridge\b", re.IGNORECASE),
    re.compile(r"\bcc\b", re.IGNORECASE),
    re.compile(r"\bchess club\b", re.IGNORECASE),
)

ONLINE_PLATFORM_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    ("Lichess", (re.compile(r"lichess(?:\.org)?", re.IGNORECASE),)),
    ("Playchess", (re.compile(r"playchess(?:\.com)?", re.IGNORECASE),)),
    ("Chess.com", (re.compile(r"chess\.com", re.IGNORECASE),)),
    ("GameKnot", (re.compile(r"gameknot(?:\.com)?", re.IGNORECASE),)),
    ("GameColony", (re.compile(r"gamecolony(?:\.com)?", re.IGNORECASE),)),
    ("ChessWorld", (re.compile(r"chessworld(?:\.net)?", re.IGNORECASE),)),
    ("KingChess", (re.compile(r"kingchess(?:\.de)?", re.IGNORECASE),)),
    ("RedHotPawn", (re.compile(r"redhotpawn(?:\.com)?", re.IGNORECASE),)),
    ("CHESS.AC", (re.compile(r"chess\.ac", re.IGNORECASE),)),
    ("ICC", (re.compile(r"(?<![a-z0-9])icc(?![a-z0-9])", re.IGNORECASE),)),
    ("Email", (re.compile(r"(?<![a-z0-9])email(?![a-z0-9])", re.IGNORECASE),)),
    ("Skype", (re.compile(r"(?<![a-z0-9])skype(?![a-z0-9])", re.IGNORECASE),)),
    (
        "Phone",
        (
            re.compile(r"(?<![a-z0-9])phone(?![a-z0-9])", re.IGNORECASE),
            re.compile(r"(?<![a-z0-9])mobile(?![a-z0-9])", re.IGNORECASE),
        ),
    ),
    ("Fritz", (re.compile(r"(?<![a-z0-9])fritz(?![a-z0-9])", re.IGNORECASE),)),
)


@dataclass(slots=True)
class PgnChunk:
    text: str


@dataclass(slots=True)
class PlayerAliasState:
    aliases: dict[str, str]
    next_index: int = 1

    def alias_for(self, player_name: str) -> str:
        normalized = player_name.strip().lower()
        if not normalized:
            return player_name
        if normalized in SAFE_PLAYER_NAMES:
            return player_name
        existing = self.aliases.get(normalized)
        if existing is not None:
            return existing
        alias = f"Player_{self.next_index:04d}"
        self.aliases[normalized] = alias
        self.next_index += 1
        return alias


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a public-safe anonymised PGN copy.")
    parser.add_argument("--input", type=Path, default=Path("pgn/all.pgn"), help="Source PGN file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pgn/public_anonymised.pgn"),
        help="Output PGN file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"PGN file not found: {args.input}")

    anonymize_pgn(args.input, args.output)


def anonymize_pgn(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    chunks = _split_pgn_chunks(text)
    alias_state = PlayerAliasState(aliases={})

    anonymised_chunks = [
        _anonymize_chunk(chunk.text, alias_state)
        for chunk in chunks
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = "\n\n".join(chunk.strip() for chunk in anonymised_chunks if chunk.strip()) + "\n"
    output_path.write_text(output_text, encoding="utf-8", newline="\n")
    print(f"Wrote {len(anonymised_chunks)} anonymised game(s) to {output_path}")


def _split_pgn_chunks(text: str) -> list[PgnChunk]:
    lines = text.splitlines()
    chunks: list[PgnChunk] = []
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("[Event ") and current_lines:
            chunks.append(PgnChunk(text="\n".join(current_lines).strip()))
            current_lines = []
        if current_lines or line.strip():
            current_lines.append(line)

    if current_lines:
        chunks.append(PgnChunk(text="\n".join(current_lines).strip()))

    return chunks


def _anonymize_chunk(chunk_text: str, alias_state: PlayerAliasState) -> str:
    header_lines, body_lines = _split_headers_and_body(chunk_text)
    headers = _parse_headers(header_lines)

    online_platform = _detect_online_platform(headers)
    is_online = online_platform is not None

    white = headers.get("White", "")
    black = headers.get("Black", "")
    if is_online:
        safe_white = _preserve_or_alias_public_handle(white, alias_state)
        safe_black = _preserve_or_alias_public_handle(black, alias_state)
    else:
        safe_white = alias_state.alias_for(white)
        safe_black = alias_state.alias_for(black)

    headers["White"] = safe_white
    headers["Black"] = safe_black

    headers["Site"] = _anonymize_site(headers.get("Site", ""), is_online, online_platform)
    headers["Event"] = _anonymize_event(headers.get("Event", ""), is_online, online_platform)

    rebuilt_headers = [
        _rebuild_header_line(name, value)
        for name, value in _headers_in_original_order(header_lines, headers)
    ]
    parts = ["\n".join(rebuilt_headers)]
    if body_lines:
        parts.append("\n".join(body_lines))
    return "\n\n".join(parts).strip()


def _split_headers_and_body(chunk_text: str) -> tuple[list[str], list[str]]:
    lines = chunk_text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            return lines[:index], [body_line for body_line in lines[index + 1 :] if body_line is not None]
    return lines, []


def _parse_headers(header_lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in header_lines:
        match = HEADER_LINE_PATTERN.match(line.strip())
        if match:
            headers[match.group("name")] = match.group("value")
    return headers


def _headers_in_original_order(
    header_lines: list[str],
    updated_headers: dict[str, str],
) -> list[tuple[str, str]]:
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in header_lines:
        match = HEADER_LINE_PATTERN.match(line.strip())
        if not match:
            continue
        name = match.group("name")
        ordered.append((name, updated_headers.get(name, match.group("value"))))
        seen.add(name)

    for required_name in ("Event", "Site", "Date", "Round", "White", "Black", "Result"):
        if required_name not in seen and required_name in updated_headers:
            ordered.append((required_name, updated_headers[required_name]))
    return ordered


def _rebuild_header_line(name: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'[{name} "{escaped}"]'


def _detect_online_platform(headers: dict[str, str]) -> str | None:
    values = [headers.get("Site", ""), headers.get("Event", "")]
    candidate_values = [value.strip() for value in values if value and value.strip()]
    for platform_name, patterns in ONLINE_PLATFORM_RULES:
        if any(pattern.search(candidate) for candidate in candidate_values for pattern in patterns):
            return platform_name
    return None


def _preserve_or_alias_public_handle(player_name: str, alias_state: PlayerAliasState) -> str:
    cleaned = player_name.strip()
    if not cleaned:
        return cleaned
    if cleaned.lower() in SAFE_PLAYER_NAMES:
        return cleaned
    if " " in cleaned:
        return alias_state.alias_for(cleaned)
    return cleaned


def _anonymize_site(site: str, is_online: bool, online_platform: str | None) -> str:
    cleaned = site.strip()
    if not cleaned:
        return cleaned
    if is_online:
        return _replace_chess_club_fragments(cleaned)
    if _looks_like_chess_club(cleaned):
        return "Chess Club"
    return "Over-the-board"


def _anonymize_event(event: str, is_online: bool, online_platform: str | None) -> str:
    cleaned = event.strip()
    if not cleaned:
        return cleaned
    if is_online:
        return _replace_chess_club_fragments(cleaned)
    if _looks_like_chess_club(cleaned):
        return "Chess Club"
    return "Over-the-board"


def _looks_like_chess_club(value: str) -> bool:
    return any(pattern.search(value) for pattern in CHESS_CLUB_PATTERNS)


def _replace_chess_club_fragments(value: str) -> str:
    updated = value
    updated = re.sub(r"\bBridge\s*C\.?C\.?\b", "Chess Club", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\bBridge\b", "Chess Club", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\bCC\b", "Chess Club", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\s{2,}", " ", updated).strip()
    return updated


if __name__ == "__main__":
    main()
