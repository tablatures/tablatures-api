
import json
import logging
import threading
from pathlib import Path
from typing import Optional
from api.models import DatabaseIndex, DatabaseMetadata, DatabaseSchema

logger = logging.getLogger(__name__)


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
        """Load database from JSON file"""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._db_data = DatabaseSchema(**data)
                logger.info("Database loaded successfully from %s", self.db_path)
            else:
                # Create empty database if file doesn't exist
                self._db_data = DatabaseSchema(
                    metadata=DatabaseMetadata(
                        lastUpdated="1970-01-01T00:00:00Z",
                        totalTabs=0,
                        version="1.0.0"
                    ),
                    tabs={},
                    index=DatabaseIndex()
                )
                logger.warning("Database file not found at %s, using empty database", self.db_path)
        except Exception as e:
            logger.error("Error loading database: %s", e)
            # Fallback to empty database
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
        """Reload database from file"""
        self._load_database()
