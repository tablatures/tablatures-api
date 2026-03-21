
import re
import logging
from typing import Set, List, Optional
from api.models import SearchQuery, SearchResponse, TabRequestResult
from api.database import DatabaseManager

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,
                prev_row[j + 1] + 1,
                prev_row[j] + cost
            ))
        prev_row = curr_row
    return prev_row[-1]


def fuzzy_match(query: str, target: str, max_distance: int = 2) -> bool:
    """Check if query fuzzy-matches any word in target within max_distance."""
    query_words = query.lower().split()
    target_words = target.lower().split()

    for qw in query_words:
        matched = False
        for tw in target_words:
            # Exact substring match
            if qw in tw:
                matched = True
                break
            # Levenshtein on short words (avoid expensive computation on long strings)
            if len(qw) >= 3 and len(tw) >= 3:
                dist = levenshtein_distance(qw, tw)
                threshold = 1 if len(qw) <= 4 else max_distance
                if dist <= threshold:
                    matched = True
                    break
        if not matched:
            return False
    return True


class SearchService:
    def __init__(self):
        self.db = DatabaseManager()

    def parse_query_string(self, q: str) -> SearchQuery:
        """Parse search query string into structured format"""
        regex = re.compile(r'\b(artist|song|album|source):([^\s]+)', re.IGNORECASE)
        result = SearchQuery()

        used_indexes = set()

        for match in regex.finditer(q):
            field_type = match.group(1).lower()
            value = match.group(2).lower()

            if field_type == "artist":
                result.artists.append(value)
            elif field_type == "song":
                result.songs.append(value)
            elif field_type == "album":
                result.albums.append(value)
            elif field_type == "source":
                result.sources.append(value)

            # Mark indexes as used
            for i in range(match.start(), match.end()):
                used_indexes.add(i)

        # Extract remaining text as naive words
        remaining = ''.join(char for i, char in enumerate(q) if i not in used_indexes).strip()

        if remaining:
            result.naive_words = [
                word for word in remaining.lower().split()
                if len(word) > 1
            ]

        return result

    def add_from_index(self, candidate_ids: Set[str], index: dict, values: List[str]):
        """Add matching IDs from index to candidate set"""
        for val in values:
            if val in index:
                for tab_id in index[val]:
                    candidate_ids.add(tab_id)

    def search_tabs(
        self,
        query: str,
        limit: int = 50,
        page: int = 1,
        source_filter: Optional[str] = None,
        artist_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        sort: str = "relevance",
    ) -> SearchResponse:
        """Search tabs based on query with optional filters and sort."""
        offset = (page - 1) * limit
        parsed = self.parse_query_string(query)

        # Apply filter params alongside parsed query filters
        if source_filter:
            parsed.sources.append(source_filter.lower())
        if artist_filter:
            parsed.artists.append(artist_filter.lower())

        candidate_ids = set()

        # Typed searches via index
        self.add_from_index(candidate_ids, self.db.data.index.artist, parsed.artists)
        self.add_from_index(candidate_ids, self.db.data.index.title, parsed.songs)
        self.add_from_index(candidate_ids, self.db.data.index.album, parsed.albums)

        # Naive words search with fuzzy matching
        fuzzy_close_matches: List[tuple] = []  # (distance, label) for did-you-mean
        used_fuzzy = False
        if parsed.naive_words:
            naive_query = ' '.join(parsed.naive_words)
            for tab_id, tab in self.db.data.tabs.items():
                text = f"{tab.title} {tab.artist or ''} {tab.album or ''}".lower()
                # Exact substring match first (fast path)
                if all(word in text for word in parsed.naive_words):
                    candidate_ids.add(tab_id)
                # Fuzzy match fallback
                elif fuzzy_match(naive_query, text):
                    candidate_ids.add(tab_id)
                    used_fuzzy = True
                else:
                    # Track near-misses for did-you-mean suggestions
                    for qw in parsed.naive_words:
                        for field_val in [tab.title, tab.artist, tab.album]:
                            if not field_val:
                                continue
                            for tw in field_val.lower().split():
                                if len(qw) >= 3 and len(tw) >= 3:
                                    dist = levenshtein_distance(qw, tw)
                                    if dist <= 3:
                                        fuzzy_close_matches.append((dist, field_val))

        # Filter results
        results = []
        type_filter_lower = type_filter.lower() if type_filter else None
        for tab_id in candidate_ids:
            if tab_id in self.db.data.tabs:
                tab = self.db.data.tabs[tab_id]
                # Source filter
                if (parsed.sources and
                        not (tab.source and tab.source.lower() in parsed.sources)):
                    continue
                # Type filter
                if type_filter_lower and (
                        not tab.type or tab.type.lower() != type_filter_lower):
                    continue
                results.append(tab)

        # Score results
        query_lower = query.lower().strip()
        scored_results = []
        for tab in results:
            score = 0
            text = f"{tab.title} {tab.artist or ''} {tab.album or ''}".lower()

            # Exact full phrase match bonus
            if query_lower in text:
                score += 100

            # Exact title match
            if tab.title.lower() == query_lower:
                score += 200

            # Naive words scoring
            for word in parsed.naive_words:
                if word in text:
                    score += 10
                    # Boost longer word matches, penalize very short partial matches
                    if len(word) >= 4:
                        score += 5
                elif len(word) >= 3:
                    # Fuzzy match gives lower score
                    words_in_text = text.split()
                    for tw in words_in_text:
                        if len(tw) >= 3 and levenshtein_distance(word, tw) <= 2:
                            score += 3
                            break

            # Exact field matches scoring
            for artist in parsed.artists:
                if tab.artist and tab.artist.lower() == artist:
                    score += 50

            for song in parsed.songs:
                if tab.title.lower() == song:
                    score += 50

            for album in parsed.albums:
                if tab.album and tab.album.lower() == album:
                    score += 30

            for source in parsed.sources:
                if tab.source and tab.source.lower() == source:
                    score += 20

            scored_results.append(TabRequestResult(
                id=tab.id,
                title=tab.title,
                artist=tab.artist,
                album=tab.album,
                type=tab.type,
                source=tab.source,
                searchTerms=tab.search_terms,
                score=score
            ))

        # Sort
        if sort == "alphabetical":
            scored_results.sort(key=lambda x: x.title.lower())
        elif sort == "newest":
            # No date field available, fall back to reverse ID order as proxy
            scored_results.sort(key=lambda x: x.id, reverse=True)
        else:
            # Default: relevance (score descending)
            scored_results.sort(key=lambda x: x.score, reverse=True)

        # Pagination
        paginated = scored_results[offset:offset + limit]

        total_pages = max((len(scored_results) + limit - 1) // limit, 1)

        logger.debug(
            "Search query='%s' returned %d results (page %d/%d)",
            query, len(scored_results), page, total_pages
        )

        # Generate "did you mean?" suggestions when no results and fuzzy was attempted
        suggestions = None
        if len(scored_results) == 0 and fuzzy_close_matches:
            # Sort by distance, deduplicate, take top 3
            fuzzy_close_matches.sort(key=lambda x: x[0])
            seen = set()
            suggestions = []
            for dist, label in fuzzy_close_matches:
                label_lower = label.lower()
                if label_lower not in seen:
                    seen.add(label_lower)
                    suggestions.append(label)
                if len(suggestions) >= 3:
                    break

        return SearchResponse(
            results=paginated,
            total=len(scored_results),
            page=page,
            limit=limit,
            totalPages=total_pages,
            suggestions=suggestions if suggestions else None,
        )
