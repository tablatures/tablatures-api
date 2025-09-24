
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
