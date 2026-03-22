"""Utilities for parsing compound artist names and extracting artists from titles."""
import re

# Separators that indicate multiple artists
_SEPARATORS = re.compile(
    r'\s*(?:,\s+|&|\|)\s*'
    r'|\s+(?:feat\.?|ft\.?|featuring|vs\.?|with)\s+',
    re.IGNORECASE
)

# Known artist names that contain separators (don't split these)
_COMPOUND_ARTISTS = {'ac/dc', 'simon & garfunkel', 'hall & oates', 'guns n\' roses'}

# Patterns for extracting real artist from title
# Matches: "Song - Artist", "Song - Artist by Transcriber", "Song (Artist)"
_TITLE_ARTIST_PATTERNS = [
    # "G.O.A.T - Polyphia by Guitarjunkey1" → artist="Polyphia"
    re.compile(r'^.+\s*-\s*(.+?)(?:\s+by\s+.+)?$', re.IGNORECASE),
    # "Song by Artist" (when the "artist" field looks like a username)
    re.compile(r'^.+\s+by\s+(.+)$', re.IGNORECASE),
]

# Heuristic: artist names that look like usernames/transcribers (not real artists)
_USERNAME_PATTERNS = re.compile(
    r'^[a-z0-9_]{3,20}\d{1,4}$'  # e.g. "guitarjunkey1", "tabmaster42"
    r'|^[A-Z][a-z]+[A-Z]'         # e.g. "GuitarJunkey" (camelCase)
    r'|\d{3,}$',                   # ends with 3+ digits
    re.IGNORECASE
)


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


def looks_like_username(name: str) -> bool:
    """Check if a name looks like a transcriber username rather than a real artist."""
    if not name:
        return False
    return bool(_USERNAME_PATTERNS.search(name.strip()))


def extract_artists_from_title(title: str, artist: str) -> list:
    """Try to extract real artist names from the title when the artist field
    might be a transcriber username.

    Examples:
        title="G.O.A.T - Polyphia by Guitarjunkey1", artist="Guitarjunkey1"
        → ["Polyphia"]

        title="Neon - John Mayer", artist="some_user123"
        → ["John Mayer"]

        title="Master of Puppets", artist="Metallica"
        → [] (artist looks real, no extraction needed)

    Returns a list of candidate artist names found in the title, or empty
    list if the existing artist looks legitimate.
    """
    if not title:
        return []

    candidates = []

    # Pattern: "Song - Artist" or "Song - Artist by Transcriber"
    m = re.match(r'^.+?\s*[-–—]\s*(.+?)(?:\s+by\s+\S+.*)?$', title, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        # Remove trailing version markers like "V1", "(2)", etc.
        candidate = re.sub(r'\s*(?:V\d+|\(\d+\)|\(Live\)|\(Solo\)|\(Intro\))$', '', candidate, flags=re.IGNORECASE).strip()
        if candidate and len(candidate) > 1:
            candidates.append(candidate)

    # Pattern: title contains well-known separator " by " before the transcriber
    # e.g. "Polyphia G.O.A.T by SomeUser" — extract "Polyphia"
    m2 = re.match(r'^(.+?)\s+by\s+\S+', title, re.IGNORECASE)
    if m2:
        # The part before "by" might contain "Artist Song" — take first word(s) as candidate
        before_by = m2.group(1).strip()
        if before_by and before_by not in candidates:
            candidates.append(before_by)

    return candidates


def get_all_candidate_artists(title: str, artist: str) -> list:
    """Get all possible artist names to try for image lookup.

    Returns a prioritized list:
    1. The original artist name
    2. Individual parts if compound (feat/&/,)
    3. Artists extracted from title (if artist looks like username)
    4. Artists extracted from title regardless (as last resort)
    """
    results = []

    # Original artist and its parts
    if artist:
        results.append(artist)
        parts = parse_artists(artist)
        for p in parts:
            if p not in results:
                results.append(p)

    # If artist looks like a username, try title extraction with higher priority
    title_candidates = extract_artists_from_title(title, artist)
    if looks_like_username(artist):
        # Insert title candidates right after the original artist
        for c in title_candidates:
            if c not in results:
                results.insert(1, c)  # Higher priority
    else:
        # Append as lower-priority fallback
        for c in title_candidates:
            if c not in results:
                results.append(c)

    return results
