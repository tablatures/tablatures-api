
import random
import re
import logging
from collections import Counter, defaultdict
from typing import Optional, List, Set, Dict, Union
from api.models import (
    TabDetailResponse, StatsResponse, SourceStats, TopArtist,
    ArtistEntry, ArtistResponse, RandomResponse,
    RecommendationGroup, RecommendationResponse,
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

    def _tab_to_detail(self, tab) -> TabDetailResponse:
        """Convert a tab record to a TabDetailResponse."""
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

    def _find_similar_artists(self, artists: List[str], exclude_artists: Set[str]) -> Dict[str, str]:
        """Find artists similar to the given ones based on source patterns and album keywords.

        Returns a dict mapping similar_artist_lower -> reason_artist (the input artist they're similar to).
        """
        tabs = self.db.data.tabs
        artist_index = self.db.data.index.artist

        # Build profiles for input artists: source patterns and album keywords
        input_profiles: Dict[str, dict] = {}
        for artist in artists:
            artist_lower = artist.lower()
            tab_ids = artist_index.get(artist_lower, [])
            sources: Counter = Counter()
            album_words: Set[str] = set()
            for tid in tab_ids:
                if tid in tabs:
                    t = tabs[tid]
                    if t.source:
                        sources[t.source] += 1
                    if t.album:
                        words = set(re.findall(r'[a-z]+', t.album.lower()))
                        # Filter out very short or common words
                        album_words.update(w for w in words if len(w) > 3)
            input_profiles[artist_lower] = {
                "display_name": artist,
                "sources": set(sources.keys()),
                "album_words": album_words,
            }

        # Score all other artists by similarity
        similar: Dict[str, str] = {}  # similar_artist_lower -> reason display name
        for other_artist_lower, other_tab_ids in artist_index.items():
            if other_artist_lower in exclude_artists:
                continue
            # Build profile for this candidate
            other_sources: Set[str] = set()
            other_album_words: Set[str] = set()
            for tid in other_tab_ids:
                if tid in tabs:
                    t = tabs[tid]
                    if t.source:
                        other_sources.add(t.source)
                    if t.album:
                        words = set(re.findall(r'[a-z]+', t.album.lower()))
                        other_album_words.update(w for w in words if len(w) > 3)

            # Check similarity against each input artist
            best_score = 0
            best_reason = ""
            for artist_lower, profile in input_profiles.items():
                score = 0
                # Source overlap
                source_overlap = len(profile["sources"] & other_sources)
                score += source_overlap * 2
                # Album keyword overlap
                word_overlap = len(profile["album_words"] & other_album_words)
                score += word_overlap
                if score > best_score:
                    best_score = score
                    best_reason = profile["display_name"]

            if best_score >= 2:
                similar[other_artist_lower] = best_reason

        return similar

    def _cap_per_artist(self, tab_ids: List[str], cap: int = 3) -> List[str]:
        """Cap tabs per artist for diversity."""
        tabs = self.db.data.tabs
        artist_counts: Counter = Counter()
        result = []
        for tid in tab_ids:
            if tid not in tabs:
                continue
            artist_key = (tabs[tid].artist or "").lower()
            if artist_counts[artist_key] < cap:
                result.append(tid)
                artist_counts[artist_key] += 1
        return result

    def get_recommendations(self, artists: List[str], exclude: Set[str], limit: int = 20) -> Union[RecommendationResponse, RandomResponse]:
        """Get recommended tabs based on favorite artists with smart grouping.

        Budget: 40% same-artist, 35% similar-artists, 25% random discovery.
        Caps at 3 tabs per individual artist for diversity.
        Returns RecommendationResponse with grouped results.
        """
        tabs = self.db.data.tabs
        if not tabs:
            return RecommendationResponse(groups=[], total=0)

        artist_index = self.db.data.index.artist
        input_artists_lower = {a.lower() for a in artists}

        # Budget allocation
        budget_artist = max(1, int(limit * 0.40))
        budget_similar = max(1, int(limit * 0.35))
        budget_discover = max(1, limit - budget_artist - budget_similar)

        groups: List[RecommendationGroup] = []
        used_ids: Set[str] = set(exclude)

        # --- 1. Same-artist tabs (40%) ---
        for artist in artists:
            artist_lower = artist.lower()
            candidate_ids = [
                tid for tid in artist_index.get(artist_lower, [])
                if tid not in used_ids
            ]
            random.shuffle(candidate_ids)
            # Cap per-artist share of the artist budget
            per_artist_limit = min(3, max(1, budget_artist // len(artists)))
            selected = candidate_ids[:per_artist_limit]

            if selected:
                results = [self._tab_to_detail(tabs[tid]) for tid in selected if tid in tabs]
                if results:
                    groups.append(RecommendationGroup(
                        reason=f"Because you like {artist}",
                        reasonType="artist",
                        results=results,
                    ))
                    used_ids.update(selected)

        # --- 2. Similar-artist tabs (35%) ---
        similar_map = self._find_similar_artists(artists, input_artists_lower)
        if similar_map:
            # Group similar artists by the reason (input artist)
            reason_groups: Dict[str, List[str]] = defaultdict(list)
            for sim_artist_lower, reason_artist in similar_map.items():
                reason_groups[reason_artist].append(sim_artist_lower)

            similar_collected: Dict[str, List[str]] = defaultdict(list)  # reason -> tab_ids
            for reason_artist, sim_artists in reason_groups.items():
                for sim_artist_lower in sim_artists:
                    candidate_ids = [
                        tid for tid in artist_index.get(sim_artist_lower, [])
                        if tid not in used_ids
                    ]
                    random.shuffle(candidate_ids)
                    similar_collected[reason_artist].extend(candidate_ids[:3])

            # Distribute similar budget across reason groups
            for reason_artist, tid_list in similar_collected.items():
                capped = self._cap_per_artist(tid_list, cap=3)
                per_group_limit = max(1, budget_similar // max(len(similar_collected), 1))
                selected = capped[:per_group_limit]
                if selected:
                    results = [self._tab_to_detail(tabs[tid]) for tid in selected if tid in tabs]
                    if results:
                        groups.append(RecommendationGroup(
                            reason=f"Similar to {reason_artist}",
                            reasonType="similar",
                            results=results,
                        ))
                        used_ids.update(selected)

        # --- 3. Random discovery (25%) ---
        all_remaining = [tid for tid in tabs.keys() if tid not in used_ids]
        if all_remaining:
            random.shuffle(all_remaining)
            capped = self._cap_per_artist(all_remaining, cap=3)
            discover_selected = capped[:budget_discover]
            if discover_selected:
                results = [self._tab_to_detail(tabs[tid]) for tid in discover_selected if tid in tabs]
                if results:
                    groups.append(RecommendationGroup(
                        reason="Discover something new",
                        reasonType="discover",
                        results=results,
                    ))

        total = sum(len(g.results) for g in groups)
        return RecommendationResponse(groups=groups, total=total)

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
