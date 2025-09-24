
import re
from typing import Set, List
from api.models import SearchQuery, SearchResponse, TabResult, TabRequestResult
from api.database import DatabaseManager

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
    
    def search_tabs(self, query: str, limit: int = 50, page: int = 1) -> dict:
        """Search tabs based on query"""
        offset = (page - 1) * limit
        parsed = self.parse_query_string(query)
        
        candidate_ids = set()
        
        # Typed searches
        self.add_from_index(candidate_ids, self.db.data.index.artist, parsed.artists)
        self.add_from_index(candidate_ids, self.db.data.index.title, parsed.songs)
        self.add_from_index(candidate_ids, self.db.data.index.album, parsed.albums)
        
        # Naive words search
        if parsed.naive_words:
            for tab_id, tab in self.db.data.tabs.items():
                text = f"{tab.title} {tab.artist or ''} {tab.album or ''}".lower()
                if all(word in text for word in parsed.naive_words):
                    candidate_ids.add(tab_id)
        
        # Filter results and apply source filter
        results = []
        for tab_id in candidate_ids:
            if tab_id in self.db.data.tabs:
                tab = self.db.data.tabs[tab_id]
                if (not parsed.sources or 
                    (tab.source and tab.source.lower() in parsed.sources)):
                    results.append(tab)
        
        # Score results
        scored_results = []
        for tab in results:
            score = 0
            text = f"{tab.title} {tab.artist or ''} {tab.album or ''}".lower()
            
            # Naive words scoring
            for word in parsed.naive_words:
                if word in text:
                    score += 10
            
            # Exact matches scoring
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
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x.score, reverse=True)
        
        # Pagination
        paginated = scored_results[offset:offset + limit]
        
        return SearchResponse(
            results=paginated,
            total=len(scored_results),
            page=page,
            limit=limit,
            totalPages=(len(scored_results) + limit - 1) // limit
        )
        
        """
            "results": paginated,
            "total": len(scored_results),
            "page": page,
            "limit": limit,
            "totalPages": (len(scored_results) + limit - 1) // limit
        }
        """