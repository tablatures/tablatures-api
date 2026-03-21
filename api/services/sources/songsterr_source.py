import logging
from typing import List

import requests

from api.services.sources.base_source import BaseSource, LiveSearchResult

logger = logging.getLogger(__name__)


class SongsterrSource(BaseSource):
    name = "songsterr"
    base_url = "https://www.songsterr.com"
    timeout = 10

    SEARCH_URL = "https://www.songsterr.com/api/songs"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def search(self, query: str, limit: int = 20) -> List[LiveSearchResult]:
        """Search Songsterr for tabs matching query."""
        try:
            resp = requests.get(
                self.SEARCH_URL,
                params={"pattern": query, "size": min(limit, 50)},
                headers=self.HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Songsterr search failed for query='%s': %s", query, exc)
            return []
        except (ValueError, KeyError) as exc:
            logger.warning("Songsterr response parse error: %s", exc)
            return []

        results: List[LiveSearchResult] = []
        for item in data[:limit]:
            song_id = item.get("id") or item.get("songId")
            title = item.get("title", "")
            artist_obj = item.get("artist") or {}
            artist_name = (
                artist_obj.get("name", "") if isinstance(artist_obj, dict) else str(artist_obj)
            )

            # Build the tab URL on songsterr
            source_url = f"{self.base_url}/a/wsa/{artist_name}-{title}-tab-s{song_id}" if song_id else self.base_url

            # Extract instrument info if present
            instruments = None
            if "tracks" in item and isinstance(item["tracks"], list):
                instruments = list({
                    t.get("instrument", "")
                    for t in item["tracks"]
                    if t.get("instrument")
                })

            track_count = None
            if "tracks" in item and isinstance(item["tracks"], list):
                track_count = len(item["tracks"])

            results.append(LiveSearchResult(
                title=title,
                artist=artist_name,
                source="songsterr",
                source_url=source_url,
                tab_type="Guitar Pro",
                track_count=track_count,
                instruments=instruments,
            ))

        return results

    def is_available(self) -> bool:
        """Check if Songsterr API is reachable."""
        try:
            resp = requests.get(
                self.SEARCH_URL,
                params={"pattern": "test", "size": 1},
                headers=self.HEADERS,
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
