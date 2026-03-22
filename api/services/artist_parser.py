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

# Heuristic: artist names that look like usernames/transcribers (not real artists)
_USERNAME_PATTERNS = re.compile(
    r'^[a-z0-9_]{3,20}\d{1,4}$'  # e.g. "guitarjunkey1", "tabmaster42"
    r'|^[A-Z][a-z]+[A-Z]'         # e.g. "GuitarJunkey" (camelCase)
    r'|\d{3,}$',                   # ends with 3+ digits
    re.IGNORECASE
)

# Trailing noise to strip from artist names
_ARTIST_TRAILING_NOISE = re.compile(
    r'\s*[-_]\s*\d+$'          # "Polyphia-2", "Artist_3"
    r'|\s+\d+$'                # "Artist 2"
    r'|\s*\(\d+\)$',           # "Artist (2)"
    re.IGNORECASE
)

# Trailing noise to strip from song titles
_TITLE_TRAILING_NOISE = re.compile(
    r'\s*(?:V\d+|\(\d+\)|\(Live\)|\(Solo\)|\(Intro\)|\(Outro\)|\(Acoustic\)|\(Part\s*\d*\))$',
    re.IGNORECASE
)


def clean_artist_name(name: str) -> str:
    """Clean an artist name by removing trailing version numbers and noise.

    Examples:
        "Polyphia-2" -> "Polyphia"
        "Artist_3" -> "Artist"
        "Artist (2)" -> "Artist"
    """
    if not name:
        return name
    cleaned = _ARTIST_TRAILING_NOISE.sub('', name).strip()
    return cleaned if cleaned else name


def clean_title(title: str) -> str:
    """Clean a song title by removing version/part markers.

    Examples:
        "Chimera (intro)" -> "Chimera"
        "Song V2" -> "Song"
    """
    if not title:
        return title
    cleaned = _TITLE_TRAILING_NOISE.sub('', title).strip()
    return cleaned if cleaned else title


def parse_artists(raw: str) -> list:
    """Split compound artist string into individual artist names,
    cleaning each one.

    Examples:
        "Y2K, bbno$" -> ["Y2K", "bbno$"]
        "Tim Henson feat. Ichika" -> ["Tim Henson", "Ichika"]
        "AC/DC" -> ["AC/DC"]
        "Polyphia-2" -> ["Polyphia"]
    """
    if not raw or not raw.strip():
        return []
    raw = raw.strip()
    if raw.lower() in _COMPOUND_ARTISTS:
        return [raw]
    parts = _SEPARATORS.split(raw)
    result = []
    for p in parts:
        cleaned = clean_artist_name(p.strip())
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def looks_like_username(name: str) -> bool:
    """Check if a name looks like a transcriber username rather than a real artist."""
    if not name:
        return False
    return bool(_USERNAME_PATTERNS.search(name.strip()))


def extract_artists_from_title(title: str, artist: str) -> list:
    """Try to extract real artist names from the title.

    Handles patterns like:
        "G.O.A.T - Polyphia by Guitarjunkey1" → ["Polyphia"]
        "Polyphia | So Strange" → ["Polyphia", "So Strange"]
        "Neon - John Mayer" → ["John Mayer"]
        "Song by Artist" → ["Artist"]

    Returns candidate artist names found in the title.
    """
    if not title:
        return []

    candidates = []

    # Pattern: "Artist | Song" or "Song | Artist" (pipe separator)
    if '|' in title:
        parts = [clean_artist_name(p.strip()) for p in title.split('|') if p.strip()]
        for p in parts:
            cleaned = clean_title(p)
            if cleaned and len(cleaned) > 1 and cleaned not in candidates:
                candidates.append(cleaned)

    # Pattern: "Song - Artist" or "Song - Artist by Transcriber"
    m = re.match(r'^(.+?)\s*[-–—]\s*(.+?)(?:\s+by\s+\S+.*)?$', title, re.IGNORECASE)
    if m:
        left = clean_title(m.group(1).strip())
        right = clean_artist_name(m.group(2).strip())
        # Right side is more likely the artist (e.g. "G.O.A.T - Polyphia")
        if right and len(right) > 1 and right not in candidates:
            candidates.append(right)
        # Left side could also be the artist (e.g. "Metallica - Master of Puppets")
        if left and len(left) > 1 and left not in candidates:
            candidates.append(left)

    # Pattern: "Song by Artist"
    m2 = re.match(r'^(.+?)\s+by\s+(.+)$', title, re.IGNORECASE)
    if m2:
        by_artist = clean_artist_name(m2.group(2).strip())
        if by_artist and len(by_artist) > 1 and by_artist not in candidates:
            candidates.append(by_artist)
        before_by = clean_title(m2.group(1).strip())
        if before_by and len(before_by) > 1 and before_by not in candidates:
            candidates.append(before_by)

    return candidates


def get_all_candidate_artists(title: str, artist: str) -> list:
    """Get all possible artist names to try for image lookup.

    Returns a prioritized list:
    1. Cleaned artist name (e.g. "Polyphia-2" → "Polyphia")
    2. Original artist name (if different from cleaned)
    3. Individual parts if compound (feat/&/,)
    4. Artists extracted from title (higher priority if artist looks like username)
    """
    results = []

    if artist:
        # Cleaned version first (strips trailing -2, _3, etc.)
        cleaned = clean_artist_name(artist)
        if cleaned:
            results.append(cleaned)
        if artist != cleaned and artist not in results:
            results.append(artist)
        # Compound split parts
        parts = parse_artists(artist)
        for p in parts:
            if p not in results:
                results.append(p)

    # Title-extracted candidates
    title_candidates = extract_artists_from_title(title or '', artist or '')
    if looks_like_username(artist or ''):
        # Username-like artist: title candidates get high priority
        for c in title_candidates:
            if c not in results:
                results.insert(min(1, len(results)), c)
    else:
        # Real-looking artist: title candidates as fallback
        for c in title_candidates:
            if c not in results:
                results.append(c)

    return results
