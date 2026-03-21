
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class Sources(int, Enum):
    GUITARPROTAB = 0
    GUITARPROTABORG = 1
    GPROTAB = 2


class TabResult(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    type: Optional[str] = None
    source: str
    download_url: str = Field(alias='downloadUrl')
    search_terms: Optional[str] = Field(alias='searchTerms', default=None)


class DatabaseMetadata(BaseModel):
    last_updated: str = Field(alias='lastUpdated')
    total_tabs: int = Field(alias='totalTabs')
    version: str


class DatabaseIndex(BaseModel):
    artist: Dict[str, List[str]] = Field(default_factory=dict)
    title: Dict[str, List[str]] = Field(default_factory=dict)
    album: Dict[str, List[str]] = Field(default_factory=dict)


class DatabaseSchema(BaseModel):
    metadata: DatabaseMetadata
    tabs: Dict[str, TabResult] = Field(default_factory=dict)
    index: DatabaseIndex


class SearchQuery(BaseModel):
    naive_words: List[str] = Field(default_factory=list, alias='naiveWords')
    artists: List[str] = Field(default_factory=list)
    songs: List[str] = Field(default_factory=list)
    albums: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class TabRequestResult(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    type: Optional[str] = None
    source: str
    search_terms: Optional[str] = Field(alias='searchTerms', default=None)
    score: int


class SearchResponse(BaseModel):
    results: List[TabRequestResult]
    total: int
    page: int
    limit: int
    total_pages: int = Field(alias='totalPages')
    suggestions: Optional[List[str]] = Field(default=None, description="Did-you-mean suggestions when no results found")


class AutocompleteResponse(BaseModel):
    query: str
    limit: int
    suggestions: List[Dict[str, str]]


class HealthResponse(BaseModel):
    status: str
    uptime: float
    timestamp: int


class HelloResponse(BaseModel):
    message: str


class SearchRequest(BaseModel):
    q: str = Field(min_length=2, description="Search query")
    limit: Optional[int] = Field(50, ge=1, le=100, description="Results limit")
    page: Optional[int] = Field(1, ge=1, description="Page number")


class AutocompleteRequest(BaseModel):
    q: str = Field(min_length=1, description="Search query")
    limit: Optional[int] = Field(10, ge=1, le=50, description="Results limit")


# --- New response models for Workstream 2 ---

class TabDetailResponse(BaseModel):
    """Response for single tab metadata (preview cards)."""
    id: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    type: Optional[str] = None
    source: str
    search_terms: Optional[str] = Field(alias='searchTerms', default=None)
    # Extended metadata fields
    download_url: Optional[str] = Field(alias='downloadUrl', default=None)
    track_count: Optional[int] = Field(alias='trackCount', default=None)
    instrument_type: Optional[str] = Field(alias='instrumentType', default=None)
    file_size: Optional[int] = Field(alias='fileSize', default=None)


class SourceStats(BaseModel):
    """Stats for a single source."""
    source: str
    count: int


class TopArtist(BaseModel):
    """An artist with their tab count."""
    artist: str
    count: int


class StatsResponse(BaseModel):
    """Response for database statistics."""
    total_tabs: int = Field(alias='totalTabs')
    total_artists: int = Field(alias='totalArtists')
    total_albums: int = Field(alias='totalAlbums')
    sources: List[SourceStats]
    top_artists: List[TopArtist] = Field(alias='topArtists')
    last_updated: str = Field(alias='lastUpdated')
    version: str


class ArtistEntry(BaseModel):
    """An artist with their tab count."""
    artist: str
    count: int


class ArtistResponse(BaseModel):
    """Paginated artist list."""
    artists: List[ArtistEntry]
    total: int
    page: int
    limit: int
    total_pages: int = Field(alias='totalPages')


class RandomResponse(BaseModel):
    """Response for random tabs."""
    results: List[TabDetailResponse]
    count: int


class SourceEntry(BaseModel):
    """A source with its tab count."""
    source: str
    count: int


class SourcesResponse(BaseModel):
    """Response listing available sources."""
    sources: List[SourceEntry]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = Field(alias='requestId', default=None)


# --- Live search models ---

class SourceStatus(BaseModel):
    """Status of a single source in a live search."""
    name: str
    status: str  # "ok", "error", "timeout"
    result_count: int = Field(alias='resultCount')
    response_time_ms: int = Field(alias='responseTimeMs')


class LiveSearchResultModel(BaseModel):
    """A single result from a live search."""
    title: str
    artist: str
    source: str
    source_url: str = Field(alias='sourceUrl')
    album: Optional[str] = None
    tab_type: Optional[str] = Field(alias='tabType', default=None)
    track_count: Optional[int] = Field(alias='trackCount', default=None)
    instruments: Optional[List[str]] = None
    difficulty: Optional[str] = None
    score: int = 0


class LiveSearchResponse(BaseModel):
    """Response for live search across multiple sources."""
    results: List[LiveSearchResultModel]
    total: int
    page: int
    limit: int
    total_pages: int = Field(alias='totalPages')
    sources_status: Dict[str, SourceStatus] = Field(alias='sourcesStatus')
