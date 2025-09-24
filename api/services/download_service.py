
import requests
from urllib.parse import urlparse
from typing import Generator, Optional
from api.database import DatabaseManager

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
        except:
            return False
    
    def stream_file(self, url: str) -> Generator[bytes, None, None]:
        """Stream file from URL with validation"""
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": base_url,
            "Origin": base_url,
            "Connection": "keep-alive",
        }
        
        response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
        
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