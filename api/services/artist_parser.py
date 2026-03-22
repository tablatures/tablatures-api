"""Utilities for parsing compound artist names."""
import re

# Separators that indicate multiple artists
_SEPARATORS = re.compile(
    r'\s*(?:,\s+|&|\|)\s*'
    r'|\s+(?:feat\.?|ft\.?|featuring|vs\.?|with)\s+',
    re.IGNORECASE
)

# Known artist names that contain separators (don't split these)
_COMPOUND_ARTISTS = {'ac/dc', 'simon & garfunkel', 'hall & oates', 'guns n\' roses'}


def parse_artists(raw: str) -> list:
    """Split compound artist string into individual artist names.

    Examples:
        "Y2K, bbno$" -> ["Y2K", "bbno$"]
        "Tim Henson feat. Ichika" -> ["Tim Henson", "Ichika"]
        "AC/DC" -> ["AC/DC"]
    """
    if not raw or not raw.strip():
        return []
    raw = raw.strip()
    if raw.lower() in _COMPOUND_ARTISTS:
        return [raw]
    parts = _SEPARATORS.split(raw)
    return [p.strip() for p in parts if p.strip()]
