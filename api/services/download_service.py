
import logging
import requests
from urllib.parse import urlparse
from typing import Generator, Optional
from api.database import DatabaseManager

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = {
    "guitarprotab.org",
    "www.guitarprotab.org",
    "guitarprotabs.org",
    "www.guitarprotabs.org",
    "guitarprotab.net",
    "www.guitarprotab.net",
    "gprotab.net",
    "www.gprotab.net",
    "songsterr.com",
    "www.songsterr.com",
    "gp.songsterr.com",
    "ultimate-guitar.com",
    "www.ultimate-guitar.com",
    "tabs.ultimate-guitar.com",
}


class DownloadService:
    ALLOWED_MAGIC = [
        "FICHIER GUITAR PRO v3",
        "FICHIER GUITAR PRO v4",
        "FICHIER GUITAR PRO v5",
        "<?xml"
    ]

    def __init__(self):
        self.db = DatabaseManager()
    
    def get_tab_download_url(self, tab_id: str) -> Optional[str]:
        """Get download URL for a tab"""
        if tab_id not in self.db.data.tabs:
            return None
        
        tab = self.db.data.tabs[tab_id]
        return tab.download_url if hasattr(tab, 'download_url') else None
    
    def validate_file_headers(self, content: bytes) -> bool:
        """Validate file headers against allowed magic bytes"""
        try:
            header_text = content[:128].decode('utf-8', errors='ignore')
            return any(magic in header_text for magic in self.ALLOWED_MAGIC)
        except Exception:
            return False
    
    def _validate_domain(self, url: str) -> None:
        """Validate URL domain against whitelist to prevent SSRF."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname not in ALLOWED_DOMAINS:
            logger.warning("Blocked download from disallowed domain: %s", hostname)
            raise ValueError(f"Domain not allowed: {hostname}")

    def stream_file(self, url: str) -> Generator[bytes, None, None]:
        """Stream file from URL with validation"""
        self._validate_domain(url)
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Songsterr GP files require Origin from songsterr.com
        if "gp.songsterr.com" in url:
            origin = "https://www.songsterr.com"
            referer = "https://www.songsterr.com/"
        else:
            origin = base_url
            referer = base_url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
            "Origin": origin,
            "Connection": "keep-alive",
        }
        
        response = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=30)
        
        if not response.ok:
            raise Exception(f"Failed to fetch remote file: {response.status_code}")
        
        content_type = response.headers.get('content-type', '').lower()
        
        # Check if response is not a valid file type
        invalid_types = ['text/html', 'application/json', 'text/plain']
        if any(invalid_type in content_type for invalid_type in invalid_types):
            raise Exception("Remote file is not a valid tab")
        
        # Read and validate first chunk
        first_chunk = None
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                if first_chunk is None:
                    first_chunk = chunk
                    # Validate magic bytes (commented out strict validation as in original)
                    # if not self.validate_file_headers(chunk):
                    #     raise Exception("Remote file is not a valid tab")
                yield chunk