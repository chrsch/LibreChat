"""
CSV parsing and formatting utilities for Collmex API communication.
"""


def parse_csv_response(text: str) -> list[list[str]]:
    """Parse a semicolon-delimited CSV response into rows of string lists."""
    rows: list[list[str]] = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        rows.append(_parse_csv_line(line))
    return rows


def _parse_csv_line(line: str) -> list[str]:
    """Parse a single semicolon-delimited CSV line, handling quoted fields."""
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    current.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                current.append(ch)
        else:
            if ch == '"':
                in_quotes = True
            elif ch == ';':
                fields.append("".join(current))
                current = []
            else:
                current.append(ch)
        i += 1
    fields.append("".join(current))
    return fields


def build_csv_line(fields: list[str | int | float]) -> str:
    """Build a semicolon-delimited CSV line from a list of values."""
    parts: list[str] = []
    for f in fields:
        s = str(f)
        if ';' in s or '"' in s:
            s = f'"{s.replace(chr(34), chr(34)+chr(34))}"'
        parts.append(s)
    return ";".join(parts)
