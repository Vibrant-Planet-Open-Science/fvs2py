"""Lightweight keyfile inspection helpers used by :class:`FVS.load_keyfile`.

The only question this module is trying to answer is "does the keyfile appear
to describe a single stand?". We choose to answer that question by requiring a
keyfile to contain single instances of ``STDIDENT``, ``PROCESS``, and ``STOP``.

Known limitations:

- ``COMMENT ... END`` blocks are not tracked. A free-form comment that
  happens to begin a line with the literal string ``STDIDENT`` (or similar)
  would be counted.
- ``OPEN``-based include files are not followed; only the text of the
  file passed directly to :meth:`FVS.load_keyfile` is inspected.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

_KEYWORD_RE: re.Pattern[str] = re.compile(r"^([A-Za-z]{1,10})", re.MULTILINE)
"""Match an FVS keyword token in columns 1-10 of a line.

Captures the leading run of ASCII letters at column 1, up to the 10th column.
The match stops naturally at the first non-letter (space, digit, punctuation,
end-of-line) or at the 10-letter cap, whichever comes first. Lines that do
not start with a letter (data rows, format specs, comment bodies) produce no
match.
"""

SINGLE_STAND_REQUIRED: Mapping[str, int] = MappingProxyType(
    {"STDIDENT": 1, "PROCESS": 1, "STOP": 1}
)
"""Keywords that must appear exactly this many times in a single-stand keyfile."""


def count_keywords(keyfile: str) -> dict[str, int]:
    """Count keyword occurrences in a keyfile body.

    Scans each line for a 1-10 letter token anchored at column 1 and followed
    by whitespace or end-of-line. Matches are upper-cased, so the returned
    counts are case-insensitive.

    Args:
        keyfile: Full text of the FVS keyword file.

    Returns:
        A mapping from upper-cased keyword name to the number of occurrences
        found. Keywords that do not appear are absent from the mapping.
    """
    counts: dict[str, int] = {}
    for m in _KEYWORD_RE.finditer(keyfile):
        kw = m.group(1).upper()
        counts[kw] = counts.get(kw, 0) + 1
    return counts


def validate_single_stand(keyfile: str) -> None:
    """Verify a keyfile appears to describe a single-stand simulation.

    Uses :func:`count_keywords` to check that each keyword in
    :data:`SINGLE_STAND_REQUIRED` appears exactly the required number of
    times. Missing or duplicated keywords are reported together in a single
    error.

    Args:
        keyfile: Full text of the FVS keyword file.

    Raises:
        ValueError: If any required keyword is missing or appears more times
            than expected. The error message lists every failing keyword.
    """
    counts = count_keywords(keyfile)
    errors: list[str] = []
    for kw, expected in SINGLE_STAND_REQUIRED.items():
        found = counts.get(kw, 0)
        if found == 0:
            errors.append(f"missing required keyword {kw!r}")
        elif found > expected:
            errors.append(
                f"found {found} instances of {kw!r} (expected {expected}); "
                "keyfile may define multiple stands"
            )
    if errors:
        msg = "Keyfile failed single-stand validation:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ValueError(msg)
