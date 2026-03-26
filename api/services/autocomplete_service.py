
import re
from typing import List, Dict
from api.models import AutocompleteResponse
from api.database import DatabaseManager

class AutocompleteService:
    def __init__(self):
        self.db = DatabaseManager()
        self._artist_cache: List[str] = []
        self._title_cache: List[Dict[str, str]] = []
        self._album_cache: List[str] = []
        self._cache_built = False

    def _build_cache(self):
        """Build deduplicated caches of artist names, song titles, and albums from tabs."""
        if self._cache_built:
            return
        seen_artists = set()
        seen_titles = set()
        seen_albums = set()
        for tab in self.db.data.tabs.values():
            artist = (tab.artist or "").strip()
            title = (tab.title or "").strip()
            album = (tab.album or "").strip()
            if artist and artist.lower() not in seen_artists:
                seen_artists.add(artist.lower())
                self._artist_cache.append(artist)
            if title and title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                self._title_cache.append({"title": title, "artist": artist})
            if album and album.lower() not in seen_albums:
                seen_albums.add(album.lower())
                self._album_cache.append(album)
        self._cache_built = True

    def _match_artists(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against full artist names."""
        self._build_cache()
        results = []
        # Prioritize prefix matches over substring matches
        for artist in self._artist_cache:
            if artist.lower().startswith(search):
                results.append({"type": "artist", "value": artist})
                if len(results) >= limit:
                    return results
        for artist in self._artist_cache:
            if search in artist.lower() and not artist.lower().startswith(search):
                results.append({"type": "artist", "value": artist})
                if len(results) >= limit:
                    return results
        return results

    def _match_titles(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against full song titles."""
        self._build_cache()
        results = []
        # Prioritize prefix matches over substring matches
        for entry in self._title_cache:
            if entry["title"].lower().startswith(search):
                results.append({"type": "song", "value": entry["title"], "info": entry["artist"]})
                if len(results) >= limit:
                    return results
        for entry in self._title_cache:
            if search in entry["title"].lower() and not entry["title"].lower().startswith(search):
                results.append({"type": "song", "value": entry["title"], "info": entry["artist"]})
                if len(results) >= limit:
                    return results
        return results

    def _match_albums(self, search: str, limit: int) -> List[Dict[str, str]]:
        """Match against full album names."""
        self._build_cache()
        results = []
        for album in self._album_cache:
            if search in album.lower():
                results.append({"type": "album", "value": album})
                if len(results) >= limit:
                    return results
        return results

    def get_suggestions(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions"""
        query_lower = query.lower().strip()

        # Detect prefixed queries
        prefixed_match = re.match(r'^(artist|song|album|source):(.+)', query_lower, re.IGNORECASE)
        suggestions = []

        if prefixed_match:
            field, search_term = prefixed_match.groups()
            search_term = search_term.strip().lower()

            if field == "artist":
                suggestions.extend(self._match_artists(search_term, limit))
            elif field == "song":
                suggestions.extend(self._match_titles(search_term, limit))
            elif field == "album":
                suggestions.extend(self._match_albums(search_term, limit))
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
            # Search across artists and songs, prioritize artists
            suggestions.extend(self._match_artists(query_lower, limit))
            suggestions.extend(self._match_titles(query_lower, limit))
            suggestions.extend(self._match_albums(query_lower, limit))
            suggestions = suggestions[:limit]

        return AutocompleteResponse(
            query=query,
            limit=limit,
            suggestions=suggestions,
        )