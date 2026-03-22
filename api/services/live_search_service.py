import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, List, Optional, Tuple

from api.services.sources.base_source import BaseSource, LiveSearchResult
from api.services.sources.local_source import LocalSource
from api.services.sources.songsterr_source import SongsterrSource
from api.services.sources.ultimate_guitar_source import UltimateGuitarSource

logger = logging.getLogger(__name__)

# Registry of available sources
SOURCE_REGISTRY: Dict[str, type] = {
    "local": LocalSource,
    "songsterr": SongsterrSource,
    "ultimate_guitar": UltimateGuitarSource,
}

VALID_SOURCE_NAMES = set(SOURCE_REGISTRY.keys())

# Cache TTL in seconds
CACHE_TTL = 15 * 60  # 15 minutes


class _CacheEntry:
    __slots__ = ("results", "sources_status", "created_at")

    def __init__(self, results, sources_status):
        self.results = results
        self.sources_status = sources_status
        self.created_at = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > CACHE_TTL


class LiveSearchService:
    def __init__(self):
        self._source_instances: Dict[str, BaseSource] = {}
        self._cache: Dict[str, _CacheEntry] = {}
        self._cache_lock = threading.Lock()

    def _get_source(self, name: str) -> BaseSource:
        """Lazy-instantiate and return a source adapter."""
        if name not in self._source_instances:
            cls = SOURCE_REGISTRY[name]
            self._source_instances[name] = cls()
        return self._source_instances[name]

    def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        """
        Search across multiple sources in parallel, merge and group results by song.

        Returns dict with keys: results, total, page, limit, totalPages, sourcesStatus
        """
        if sources is None:
            sources = list(SOURCE_REGISTRY.keys())
        else:
            sources = [s for s in sources if s in VALID_SOURCE_NAMES]

        # Check cache
        cache_key = f"{query.lower().strip()}|{','.join(sorted(sources))}"
        with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry and not entry.is_expired():
                logger.debug("Cache hit for live search query='%s'", query)
                all_results = entry.results
                sources_status = entry.sources_status
                return self._paginate(all_results, sources_status, page, limit)
            # Evict expired entry
            if entry:
                del self._cache[cache_key]

        # Query all sources in parallel
        all_results: List[LiveSearchResult] = []
        sources_status: Dict[str, dict] = {}

        def _query_source(name: str) -> Tuple[str, List[LiveSearchResult], dict]:
            source = self._get_source(name)
            start = time.time()
            try:
                results = source.search(query, limit=limit)
                elapsed_ms = round((time.time() - start) * 1000)
                status = {
                    "name": name,
                    "status": "ok",
                    "resultCount": len(results),
                    "responseTimeMs": elapsed_ms,
                }
                return name, results, status
            except Exception as exc:
                elapsed_ms = round((time.time() - start) * 1000)
                logger.warning("Source '%s' failed: %s", name, exc)
                status = {
                    "name": name,
                    "status": "error",
                    "resultCount": 0,
                    "responseTimeMs": elapsed_ms,
                }
                return name, [], status

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {executor.submit(_query_source, s): s for s in sources}
            for future in futures:
                source_name = futures[future]
                try:
                    name, results, status = future.result(timeout=15)
                    sources_status[name] = status
                    all_results.extend(results)
                except FuturesTimeoutError:
                    sources_status[source_name] = {
                        "name": source_name,
                        "status": "timeout",
                        "resultCount": 0,
                        "responseTimeMs": 15000,
                    }
                except Exception as exc:
                    logger.error("Unexpected error from source '%s': %s", source_name, exc)
                    sources_status[source_name] = {
                        "name": source_name,
                        "status": "error",
                        "resultCount": 0,
                        "responseTimeMs": 0,
                    }

        # Group by song instead of deduplicating
        grouped = self._group_by_song(all_results)

        # Score results
        scored = self._score_results(grouped, query)

        # Cache merged results
        with self._cache_lock:
            self._cache[cache_key] = _CacheEntry(scored, sources_status)

        return self._paginate(scored, sources_status, page, limit)

    def _group_by_song(self, results: List[LiveSearchResult]) -> List[Tuple[LiveSearchResult, List[LiveSearchResult]]]:
        """Group results by normalized artist|title instead of deduplicating.

        Returns list of (primary_result, all_variants) tuples.
        Variants are sorted: local first, then by track_count descending.
        The primary result is the first variant after sorting.
        """
        from collections import OrderedDict

        groups: Dict[str, List[LiveSearchResult]] = OrderedDict()
        for r in results:
            key = f"{r.artist.strip().lower()}|{r.title.strip().lower()}"
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        grouped: List[Tuple[LiveSearchResult, List[LiveSearchResult]]] = []
        for key, variants in groups.items():
            # Sort: local first, then by track_count descending
            variants.sort(key=lambda v: (
                0 if v.source == "local" else 1,
                -(v.track_count or 0),
            ))
            primary = variants[0]
            grouped.append((primary, variants))

        return grouped

    def _score_results(
        self, grouped_results: List[Tuple[LiveSearchResult, List[LiveSearchResult]]], query: str
    ) -> List[dict]:
        """Score and convert grouped results to serializable dicts."""
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        scored = []
        for primary, variants in grouped_results:
            score = 0
            text = f"{primary.title} {primary.artist}".lower()

            # Exact phrase match
            if query_lower in text:
                score += 100

            # Exact title match
            if primary.title.lower().strip() == query_lower:
                score += 200

            # Word matches
            for word in query_words:
                if word in text:
                    score += 10
                    if len(word) >= 4:
                        score += 5

            # Prefer local results
            if primary.source == "local":
                score += 50

            entry = {
                "id": primary.tab_id,
                "title": primary.title,
                "artist": primary.artist,
                "source": primary.source,
                "sourceUrl": primary.source_url,
                "album": primary.album,
                "tabType": primary.tab_type,
                "trackCount": primary.track_count,
                "instruments": primary.instruments,
                "difficulty": primary.difficulty,
                "score": score,
            }

            # Add variants when there are multiple sources
            if len(variants) > 1:
                entry["variants"] = [
                    {
                        "id": v.tab_id,
                        "source": v.source,
                        "sourceUrl": v.source_url,
                        "trackCount": v.track_count,
                        "instruments": v.instruments,
                    }
                    for v in variants
                ]

            scored.append(entry)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _paginate(
        self,
        scored: List[dict],
        sources_status: Dict[str, dict],
        page: int,
        limit: int,
    ) -> dict:
        """Apply pagination and build final response."""
        total = len(scored)
        total_pages = max((total + limit - 1) // limit, 1)
        offset = (page - 1) * limit
        paginated = scored[offset : offset + limit]

        return {
            "results": paginated,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
            "sourcesStatus": sources_status,
        }
