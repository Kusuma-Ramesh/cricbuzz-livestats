"""Cricket overs notation helpers.

Cricket writes 4.3 for "4 overs and 3 balls" - NOT 4.3 decimal overs. The database therefore stores
legal balls (an integer) and these helpers convert at the edges (forms and display).
"""

from __future__ import annotations

import re

_PATTERN = re.compile(r"^\s*(\d{1,3})(?:\.([0-5]))?\s*$")


def to_balls(notation: str | float | int) -> int:
    """'4.3' -> 27. Raises ValueError for impossible notation such as '4.7'."""
    m = _PATTERN.match(str(notation))
    if not m:
        raise ValueError("Overs must look like 4, 4.1 ... 4.5 (a over has only 6 legal balls).")
    return int(m.group(1)) * 6 + int(m.group(2) or 0)


def to_notation(balls: int | float | None) -> str:
    """27 -> '4.3'."""
    if balls is None:
        return ""
    b = int(balls)
    return f"{b // 6}.{b % 6}"


def economy(runs: int, balls: int) -> float | None:
    return round(runs * 6.0 / balls, 2) if balls else None
