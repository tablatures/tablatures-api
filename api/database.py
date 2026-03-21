
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional
from api.models import DatabaseIndex, DatabaseMetadata, DatabaseSchema

logger = logging.getLogger(__name__)

# Vercel Blob: URL + token for private blobs (set in Vercel environment)
DATABASE_BLOB_URL = os.environ.get("DATABASE_BLOB_URL", "")
BLOB_READ_WRITE_TOKEN = os.environ.get("DATABASE_BLOB_READ_WRITE_TOKEN", "")


class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _db_data: Optional[DatabaseSchema] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path = Path.cwd() / "database" / "database.json"
            self._load_database()
            self.initialized = True

    def _load_database(self):
        """Load database from local file or Vercel Blob."""
        # Try local file first (development)
        if self.db_path.exists():
            self._load_from_file()
            return

        # Try Vercel Blob (production)
        if DATABASE_BLOB_URL:
            self._load_from_blob()
            return

        # Fallback to empty database
        logger.warning("No database source available (no local file, no BLOB_URL)")
        self._set_empty_database()

    def _load_from_file(self):
        """Load database from local JSON file."""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._db_data = DatabaseSchema(**data)
            logger.info("Database loaded from file: %s (%d tabs)", self.db_path, len(self._db_data.tabs))
        except Exception as e:
            logger.error("Error loading database from file: %s", e)
            self._set_empty_database()

    def _load_from_blob(self):
        """Load database from Vercel Blob Storage (supports private blobs)."""
        try:
            import requests
            logger.info("Loading database from Vercel Blob: %s", DATABASE_BLOB_URL[:80])
            headers = {}
            if BLOB_READ_WRITE_TOKEN:
                headers["Authorization"] = f"Bearer {BLOB_READ_WRITE_TOKEN}"
            resp = requests.get(DATABASE_BLOB_URL, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                self._db_data = DatabaseSchema(**data)
                logger.info("Database loaded from blob (%d tabs)", len(self._db_data.tabs))
            else:
                logger.error("Blob fetch failed: HTTP %d", resp.status_code)
                self._set_empty_database()
        except Exception as e:
            logger.error("Error loading database from blob: %s", e)
            self._set_empty_database()

    def _set_empty_database(self):
        """Set an empty database as fallback."""
        self._db_data = DatabaseSchema(
            metadata=DatabaseMetadata(
                lastUpdated="1970-01-01T00:00:00Z",
                totalTabs=0,
                version="1.0.0"
            ),
            tabs={},
            index=DatabaseIndex()
        )

    @property
    def data(self) -> DatabaseSchema:
        """Get database data"""
        if self._db_data is None:
            self._load_database()
        return self._db_data

    def reload(self):
        """Reload database from source"""
        self._load_database()
