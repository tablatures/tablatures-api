
import re
import threading
from math import ceil
from typing import List, Dict, Tuple
from api.models import AutocompleteResponse
from api.database import DatabaseManager


class AutocompleteService:
    """Autocomplete service. Instantiated once at module level in the controller
    (via AutocompleteController.__init__), so caches persist for the process lifetime."""

    def __init__(self):
        self.db = DatabaseManager()
        self._artist_cache: List[str] = []
        self._title_cache: List[Dict[str, str]] = []
        self._source_cache: List[str] = []
        self._lock = threading.Lock()
        self._cache_built = False

    def _build_cache(self):
        """Build deduplicated caches of artist names, song titles, and sources from tabs."""
        if self._cache_built:
            return
        with self._lock:
            if self._cache_built:
                return
            seen_artists: set = set()
            seen_titles: set = set()
            seen_sources: set = set()
            for tab in self.db.data.tabs.values():
                artist = (tab.artist or "").strip()
                title = (tab.title or "").strip()
                source = (tab.source or "").strip()
                # Dedup titles by (title, artist) to keep same-named songs by different artists
                if title:
                    title_key = (title.lower(), artist.lower())
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        self._title_cache.append({
                            "title": title,
                            "artist": artist,
                            "search_text": title.lower() + " " + artist.lower(),
                        })
                if artist and artist.lower() not in seen_artists:
                    seen_artists.add(artist.lower())
                    self._artist_cache.append(artist)
                if source and source.lower() not in seen_sources:
                    seen_sources.add(source.lower())
                    self._source_cache.append(source)
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
                if len(prefix) >= limit:
                    break
            elif search in lower:
                substring.append({"type": "artist", "value": artist})
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
            text = entry["search_text"]
            if len(query_words) == 1:
                match = search in text
            else:
                match = all(w in text for w in query_words)
            if not match:
                continue
            item = {"type": "song", "value": entry["title"]}
            if entry["artist"]:
                item["info"] = entry["artist"]
            if title_lower.startswith(search):
                prefix.append(item)
                if len(prefix) >= limit:
                    break
            else:
                substring.append(item)
        results = prefix[:limit]
        remaining = limit - len(results)
        if remaining > 0:
            results.extend(substring[:remaining])
        return results

    def _match_albums(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against album index keys with prefix priority."""
        index = self.db.data.index.album
        if not index:
            return []
        prefix = []
        substring = []
        for key in index.keys():
            if key.startswith(search):
                prefix.append({"type": "album", "value": key})
                if len(prefix) >= limit:
                    break
            elif search in key:
                substring.append({"type": "album", "value": key})
        results = prefix[:limit]
        remaining = limit - len(results)
        if remaining > 0:
            results.extend(substring[:remaining])
        return results

    def _match_sources(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against cached source names."""
        self._build_cache()
        return [
            {"type": "source", "value": src}
            for src in self._source_cache
            if search in src.lower()
        ][:limit]

    def get_suggestions(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions."""
        query_lower = query.lower().strip()

        if not query_lower:
            return AutocompleteResponse(query=query, limit=limit, suggestions=[])

        prefixed_match = re.match(r'^(artist|song|album|source):(.+)', query_lower)
        suggestions: List[Dict[str, str]] = []

        if prefixed_match:
            field, search_term = prefixed_match.groups()
            search_term = search_term.strip().lower()

            if field == "artist":
                suggestions.extend(self._match_artists(search_term, limit))
            elif field == "song":
                suggestions.extend(self._match_songs(search_term, limit))
            elif field == "album":
                suggestions.extend(self._match_albums(search_term, limit))
            elif field == "source":
                suggestions.extend(self._match_sources(search_term, limit))
        else:
            artist_limit = ceil(limit / 2)
            song_limit = limit - artist_limit
            artists = self._match_artists(query_lower, artist_limit)
            songs = self._match_songs(query_lower, song_limit)
            # If one category has fewer results, give the slack to the other
            if len(artists) < artist_limit:
                songs = self._match_songs(query_lower, limit - len(artists))
            elif len(songs) < song_limit:
                artists = self._match_artists(query_lower, limit - len(songs))
            suggestions.extend(artists)
            suggestions.extend(songs)
            suggestions = suggestions[:limit]

        return AutocompleteResponse(
            query=query,
            limit=limit,
            suggestions=suggestions,
        )
