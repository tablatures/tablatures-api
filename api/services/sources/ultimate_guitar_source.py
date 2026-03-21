import json
import logging
import re
from typing import List
from urllib.parse import quote_plus

import requests

from api.services.sources.base_source import BaseSource, LiveSearchResult

logger = logging.getLogger(__name__)


class UltimateGuitarSource(BaseSource):
    name = "ultimate_guitar"
    base_url = "https://www.ultimate-guitar.com"
    timeout = 10

    SEARCH_URL = "https://www.ultimate-guitar.com/search.php"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # UG tab type codes for Guitar Pro formats
    GP_TYPE_CODES = {"Guitar Pro", "Power", "Pro"}

    def search(self, query: str, limit: int = 20) -> List[LiveSearchResult]:
        """Search Ultimate Guitar for Guitar Pro tabs."""
        try:
            resp = requests.get(
                self.SEARCH_URL,
                params={
                    "search_type": "title",
                    "value": query,
                },
                headers=self.HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            html_text = resp.text
        except requests.RequestException as exc:
            logger.warning("Ultimate Guitar search failed for query='%s': %s", query, exc)
            return []

        # Extract embedded JSON from data-content attribute on .js-store div
        store_data = self._extract_store_data(html_text)
        if store_data is None:
            return []

        results: List[LiveSearchResult] = []
        try:
            search_results = (
                store_data.get("store", {})
                .get("page", {})
                .get("data", {})
                .get("results", [])
            )
        except (AttributeError, TypeError):
            logger.warning("Unexpected Ultimate Guitar response structure")
            return []

        for item in search_results:
            if not isinstance(item, dict):
                continue

            tab_type = item.get("type", "")

            # Filter for Guitar Pro types specifically
            if tab_type not in self.GP_TYPE_CODES:
                continue

            title = item.get("song_name", "")
            artist = item.get("artist_name", "")
            tab_url = item.get("tab_url", "")

            results.append(LiveSearchResult(
                title=title,
                artist=artist,
                source="ultimate_guitar",
                source_url=tab_url or self.base_url,
                tab_type=tab_type,
                difficulty=item.get("difficulty"),
            ))

            if len(results) >= limit:
                break

        return results

    def _extract_store_data(self, html: str) -> dict | None:
        """Extract the JSON data embedded in the .js-store div's data-content attribute."""
        # Pattern matches: <div class="js-store" data-content="...">
        match = re.search(r'class="js-store"\s+data-content="([^"]*)"', html)
        if not match:
            logger.warning("Could not find .js-store data-content in UG response")
            return None

        raw = match.group(1)
        # The content is HTML-entity encoded JSON
        decoded = raw.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#039;", "'")

        try:
            return json.loads(decoded)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse UG store JSON: %s", exc)
            return None

    def is_available(self) -> bool:
        """Check if Ultimate Guitar is reachable."""
        try:
            resp = requests.head(
                self.base_url,
                headers=self.HEADERS,
                timeout=5,
            )
            return resp.status_code < 400
        except requests.RequestException:
            return False
