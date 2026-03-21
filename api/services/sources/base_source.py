from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class LiveSearchResult:
    title: str
    artist: str
    source: str
    source_url: str  # direct link on the external site
    album: Optional[str] = None
    tab_type: Optional[str] = None
    track_count: Optional[int] = None
    instruments: Optional[List[str]] = None
    difficulty: Optional[str] = None
    tab_id: Optional[str] = None


class BaseSource(ABC):
    name: str
    base_url: str
    timeout: int = 10  # seconds

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> List[LiveSearchResult]:
        """Search this source for tabs matching query"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Health check for this source"""
        pass
