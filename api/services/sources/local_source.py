import logging
from typing import List

from api.services.sources.base_source import BaseSource, LiveSearchResult
from api.services.search_service import SearchService

logger = logging.getLogger(__name__)


class LocalSource(BaseSource):
    name = "local"
    base_url = ""
    timeout = 5

    def __init__(self):
        self._search_service = SearchService()

    def search(self, query: str, limit: int = 20) -> List[LiveSearchResult]:
        """Delegate to existing local SearchService and wrap as LiveSearchResult."""
        try:
            # Fetch a large set from local DB - pagination is handled by LiveSearchService
            response = self._search_service.search_tabs(query, limit=500, page=1)
        except Exception as exc:
            logger.warning("Local search failed for query='%s': %s", query, exc)
            return []

        results: List[LiveSearchResult] = []
        for tab in response.results:
            results.append(LiveSearchResult(
                title=tab.title,
                artist=tab.artist or "",
                source="local",
                source_url="",
                album=tab.album,
                tab_type=tab.type,
                tab_id=tab.id,
            ))

        return results

    def is_available(self) -> bool:
        """Local database is always available."""
        return True
