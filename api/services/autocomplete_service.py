
import re
from typing import List, Dict
from api.models import AutocompleteResponse
from api.database import DatabaseManager

class AutocompleteService:
    def __init__(self):
        self.db = DatabaseManager()
        self._artist_cache: List[str] = []
        self._title_cache: List[Dict[str, str]] = []
        self._cache_built = False

    def _build_cache(self):
        """Build deduplicated caches of artist names and song titles from tabs."""
        if self._cache_built:
            return
        seen_artists = set()
        seen_titles = set()
        for tab in self.db.data.tabs.values():
            artist = (tab.artist or "").strip()
            title = (tab.title or "").strip()
            if artist and artist.lower() not in seen_artists:
                seen_artists.add(artist.lower())
                self._artist_cache.append(artist)
            if title and title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                self._title_cache.append({"title": title, "artist": artist})
        self._cache_built = True

    def _match_artists(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against full artist names with prefix priority."""
        self._build_cache()
        prefix = []
        substring = []
        for artist in self._artist_cache:
            lower = artist.lower()
            if lower.startswith(search):
                prefix.append({"type": "artist", "value": artist})
            elif search in lower:
                substring.append({"type": "artist", "value": artist})
            if len(prefix) >= limit:
                break
        results = prefix[:limit]
        remaining = limit - len(results)
        if remaining > 0:
            results.extend(substring[:remaining])
        return results

    def _match_songs(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against full song titles with prefix priority."""
        self._build_cache()
        query_words = search.split()
        prefix = []
        substring = []
        for entry in self._title_cache:
            title_lower = entry["title"].lower()
            if len(query_words) == 1:
                match = search in title_lower
            else:
                match = all(w in title_lower for w in query_words)
            if not match:
                continue
            item = {"type": "song", "value": entry["title"], "info": entry["artist"]}
            if title_lower.startswith(search):
                prefix.append(item)
            else:
                substring.append(item)
            if len(prefix) + len(substring) >= limit * 3:
                break
        results = prefix[:limit]
        remaining = limit - len(results)
        if remaining > 0:
            results.extend(substring[:remaining])
        return results

    def get_suggestions(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions"""
        query_lower = query.lower().strip()

        prefixed_match = re.match(r'^(artist|song|album|source):(.+)', query_lower, re.IGNORECASE)
        suggestions = []

        if prefixed_match:
            field, search_term = prefixed_match.groups()
            search_term = search_term.strip().lower()

            if field == "artist":
                suggestions.extend(self._match_artists(search_term, limit))
            elif field == "song":
                suggestions.extend(self._match_songs(search_term, limit))
            elif field == "source":
                all_sources = set()
                for tab in self.db.data.tabs.values():
                    if tab.source:
                        all_sources.add(tab.source)
                suggestions.extend(
                    {"type": "source", "value": src}
                    for src in all_sources
                    if search_term in src.lower()
                )
                suggestions = suggestions[:limit]
        else:
            suggestions.extend(self._match_artists(query_lower, limit))
            suggestions.extend(self._match_songs(query_lower, limit))
            suggestions = suggestions[:limit]

        return AutocompleteResponse(
            query=query,
            limit=limit,
            suggestions=suggestions,
        )
