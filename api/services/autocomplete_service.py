
import re
from typing import List, Dict
from api.models import AutocompleteResponse
from api.database import DatabaseManager

class AutocompleteService:
    def __init__(self):
        self.db = DatabaseManager()
    
    def collect_matches(self, field_type: str, index: dict, search: str, limit: int) -> List[Dict[str, str]]:
        """Collect matching entries from index"""
        matches = [
            {"type": field_type, "value": key}
            for key in index.keys()
            if search in key
        ]
        return matches[:limit]
    
    def get_suggestions(self, query: str, limit: int = 10) -> AutocompleteResponse:
        """Get autocomplete suggestions"""
        query_lower = query.lower().strip()
        
        # Detect prefixed queries
        prefixed_match = re.match(r'^(artist|song|album|source):(.+)', query_lower, re.IGNORECASE)
        suggestions = []
        
        if prefixed_match:
            field, search_term = prefixed_match.groups()
            search_term = search_term.lower()
            
            if field == "artist":
                suggestions.extend(
                    self.collect_matches("artist", self.db.data.index.artist, search_term, limit)
                )
            elif field == "song":
                suggestions.extend(
                    self.collect_matches("song", self.db.data.index.title, search_term, limit)
                )
            elif field == "album":
                suggestions.extend(
                    self.collect_matches("album", self.db.data.index.album, search_term, limit)
                )
            elif field == "source":
                all_sources = set()
                for tab in self.db.data.tabs.values():
                    if tab.source:
                        all_sources.add(tab.source.lower())
                
                matching_sources = [
                    {"type": "source", "value": src}
                    for src in all_sources
                    if search_term in src
                ]
                suggestions.extend(matching_sources[:limit])
        else:
            # Naive search across all fields
            suggestions.extend(
                self.collect_matches("artist", self.db.data.index.artist, query_lower, limit)
            )
            suggestions.extend(
                self.collect_matches("song", self.db.data.index.title, query_lower, limit)
            )
            suggestions.extend(
                self.collect_matches("album", self.db.data.index.album, query_lower, limit)
            )
        
        return AutocompleteResponse(
            query=query,
            limit=limit,
            suggestions=suggestions,
        )