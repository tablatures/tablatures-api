
import random
import logging
from collections import Counter
from typing import Optional, List, Set
from api.models import (
    TabDetailResponse, StatsResponse, SourceStats, TopArtist,
    ArtistEntry, ArtistResponse, RandomResponse,
    SourceEntry, SourcesResponse,
)
from api.database import DatabaseManager

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self):
        self.db = DatabaseManager()

    def get_tab_detail(self, tab_id: str) -> Optional[TabDetailResponse]:
        """Get tab metadata by ID (without download URL)."""
        if tab_id not in self.db.data.tabs:
            return None
        tab = self.db.data.tabs[tab_id]
        # Extract any additional metadata available on the tab object
        extra_kwargs = {}
        for attr, alias in [
            ('download_url', 'downloadUrl'),
            ('track_count', 'trackCount'),
            ('instrument_type', 'instrumentType'),
            ('file_size', 'fileSize'),
        ]:
            val = getattr(tab, attr, None)
            if val is not None:
                extra_kwargs[alias] = val
        return TabDetailResponse(
            id=tab.id,
            title=tab.title,
            artist=tab.artist,
            album=tab.album,
            type=tab.type,
            source=tab.source,
            searchTerms=tab.search_terms,
            **extra_kwargs,
        )

    def get_stats(self, top_n: int = 10) -> StatsResponse:
        """Get database statistics."""
        tabs = self.db.data.tabs
        meta = self.db.data.metadata

        # Source breakdown
        source_counter: Counter = Counter()
        artist_counter: Counter = Counter()
        for tab in tabs.values():
            if tab.source:
                source_counter[tab.source] += 1
            if tab.artist:
                artist_counter[tab.artist] += 1

        sources = [
            SourceStats(source=src, count=cnt)
            for src, cnt in source_counter.most_common()
        ]

        top_artists = [
            TopArtist(artist=art, count=cnt)
            for art, cnt in artist_counter.most_common(top_n)
        ]

        return StatsResponse(
            totalTabs=len(tabs),
            totalArtists=len(self.db.data.index.artist),
            totalAlbums=len(self.db.data.index.album),
            sources=sources,
            topArtists=top_artists,
            lastUpdated=meta.last_updated,
            version=meta.version,
        )

    def get_artists(self, page: int = 1, limit: int = 50, q: Optional[str] = None) -> ArtistResponse:
        """Get paginated artist list with tab counts."""
        artist_index = self.db.data.index.artist

        entries = []
        q_lower = q.lower() if q else None
        for artist_name, tab_ids in artist_index.items():
            if q_lower and q_lower not in artist_name.lower():
                continue
            entries.append(ArtistEntry(artist=artist_name, count=len(tab_ids)))

        # Sort alphabetically
        entries.sort(key=lambda e: e.artist.lower())

        total = len(entries)
        total_pages = max((total + limit - 1) // limit, 1)
        offset = (page - 1) * limit
        paginated = entries[offset:offset + limit]

        return ArtistResponse(
            artists=paginated,
            total=total,
            page=page,
            limit=limit,
            totalPages=total_pages,
        )

    def get_random_tabs(self, count: int = 5) -> RandomResponse:
        """Get random tabs for discover feature."""
        tabs = self.db.data.tabs
        if not tabs:
            return RandomResponse(results=[], count=0)

        tab_ids = list(tabs.keys())
        sample_size = min(count, len(tab_ids))
        sampled_ids = random.sample(tab_ids, sample_size)

        results = []
        for tab_id in sampled_ids:
            tab = tabs[tab_id]
            results.append(TabDetailResponse(
                id=tab.id,
                title=tab.title,
                artist=tab.artist,
                album=tab.album,
                type=tab.type,
                source=tab.source,
                searchTerms=tab.search_terms,
            ))

        return RandomResponse(results=results, count=len(results))

    def get_recommendations(self, artists: List[str], exclude: Set[str], limit: int = 20) -> RandomResponse:
        """Get recommended tabs based on favorite artists."""
        tabs = self.db.data.tabs
        if not tabs:
            return RandomResponse(results=[], count=0)

        artist_index = self.db.data.index.artist

        # Collect all tab IDs from the requested artists
        collected_ids: Set[str] = set()
        for artist in artists:
            artist_lower = artist.lower()
            if artist_lower in artist_index:
                collected_ids.update(artist_index[artist_lower])

        # Remove excluded IDs
        collected_ids -= exclude

        # Pick up to limit from collected
        collected_list = list(collected_ids)
        if len(collected_list) > limit:
            selected_ids = random.sample(collected_list, limit)
        else:
            selected_ids = collected_list

            # Pad with random tabs if fewer than limit
            remaining = limit - len(selected_ids)
            if remaining > 0:
                all_ids = set(tabs.keys()) - exclude - collected_ids
                pad_list = list(all_ids)
                pad_size = min(remaining, len(pad_list))
                if pad_size > 0:
                    selected_ids.extend(random.sample(pad_list, pad_size))

        results = []
        for tab_id in selected_ids:
            tab = tabs[tab_id]
            results.append(TabDetailResponse(
                id=tab.id,
                title=tab.title,
                artist=tab.artist,
                album=tab.album,
                type=tab.type,
                source=tab.source,
                searchTerms=tab.search_terms,
            ))

        return RandomResponse(results=results, count=len(results))

    def get_sources(self) -> SourcesResponse:
        """List available sources with tab counts."""
        source_counter: Counter = Counter()
        for tab in self.db.data.tabs.values():
            if tab.source:
                source_counter[tab.source] += 1

        sources = [
            SourceEntry(source=src, count=cnt)
            for src, cnt in source_counter.most_common()
        ]

        return SourcesResponse(sources=sources, total=len(sources))
