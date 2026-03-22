
import os
import time
import uuid
import logging
from collections import defaultdict
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from api.models import HealthResponse, HelloResponse
from api.controllers.search_controller import SearchController
from api.controllers.autocomplete_controller import AutocompleteController
from api.controllers.download_controller import DownloadController
from api.controllers.catalog_controller import CatalogController
from api.controllers.live_search_controller import LiveSearchController

# --- Structured logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Response compression ---
try:
    from flask_compress import Compress
    Compress(app)
    app.config['COMPRESS_MIN_SIZE'] = 500
    logger.info("Response compression enabled via flask-compress")
except ImportError:
    logger.info("flask-compress not installed, using manual gzip compression")

    import gzip

    @app.after_request
    def gzip_response(response):
        """Gzip responses larger than 500 bytes when client accepts gzip."""
        if (
            response.status_code < 200
            or response.status_code >= 300
            or response.direct_passthrough
            or len(response.get_data()) < 500
            or 'Content-Encoding' in response.headers
            or 'gzip' not in request.headers.get('Accept-Encoding', '')
        ):
            return response
        response.set_data(gzip.compress(response.get_data()))
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.get_data())
        response.headers['Vary'] = 'Accept-Encoding'
        return response

# --- CORS configuration ---
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins == '*':
    CORS(app)
else:
    CORS(app, origins=[o.strip() for o in cors_origins.split(',')])

search_controller = SearchController()
autocomplete_controller = AutocompleteController()
download_controller = DownloadController()
catalog_controller = CatalogController()
live_search_controller = LiveSearchController()

from api.controllers.metadata_controller import MetadataController
metadata_controller = MetadataController()

startup_time = time.time()

# --- Basic rate limiting middleware ---
# In-memory store: ip -> list of request timestamps
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', 100))  # requests per window
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))  # seconds


_RATE_LIMIT_EXEMPT_PATHS = {'/api/docs', '/api/v1/docs', '/api/health', '/api/v1/health'}


@app.before_request
def attach_request_id():
    """Generate a unique request ID and attach it to g for tracing."""
    g.request_id = str(uuid.uuid4())


@app.after_request
def add_request_id_header(response):
    """Include request ID in response headers."""
    request_id = getattr(g, 'request_id', None)
    if request_id:
        response.headers['X-Request-ID'] = request_id
    return response


@app.before_request
def rate_limit():
    """Basic IP-based rate limiting."""
    if request.path in _RATE_LIMIT_EXEMPT_PATHS:
        return None

    client_ip = request.remote_addr or "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Prune old entries
    timestamps = _rate_limit_store[client_ip]
    pruned = [t for t in timestamps if t > window_start]

    if not pruned:
        # Clean up empty entries to prevent memory leak
        _rate_limit_store.pop(client_ip, None)
    else:
        _rate_limit_store[client_ip] = pruned

    if len(pruned) >= RATE_LIMIT_MAX:
        logger.warning("Rate limit exceeded for %s (request_id=%s)", client_ip, getattr(g, 'request_id', None))
        return jsonify({"error": "Too many requests. Please try again later.", "requestId": getattr(g, 'request_id', None)}), 429

    _rate_limit_store[client_ip] = pruned + [now]


# --- OpenAPI / Swagger documentation ---
OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Tablatures API",
        "description": "API for searching and downloading guitar tablatures.",
        "version": "1.0.0",
    },
    "servers": [
        {"url": "/api/v1", "description": "API v1"},
        {"url": "/api", "description": "API (alias)"},
    ],
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "responses": {"200": {"description": "API is healthy"}},
            }
        },
        "/search": {
            "get": {
                "summary": "Search tabs",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string", "minLength": 2}, "description": "Search query"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 100}},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1, "minimum": 1}},
                    {"name": "source", "in": "query", "schema": {"type": "string"}, "description": "Filter by source"},
                    {"name": "artist", "in": "query", "schema": {"type": "string"}, "description": "Filter by artist"},
                    {"name": "type", "in": "query", "schema": {"type": "string"}, "description": "Filter by tab type"},
                    {"name": "sort", "in": "query", "schema": {"type": "string", "enum": ["relevance", "alphabetical", "newest"], "default": "relevance"}},
                ],
                "responses": {"200": {"description": "Search results"}},
            }
        },
        "/autocomplete": {
            "get": {
                "summary": "Autocomplete suggestions",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string", "minLength": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}},
                ],
                "responses": {"200": {"description": "Autocomplete suggestions"}},
            }
        },
        "/download/{tab_id}": {
            "get": {
                "summary": "Download a tab file",
                "parameters": [
                    {"name": "tab_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Tab file stream"},
                    "404": {"description": "Tab not found"},
                },
            }
        },
        "/tab/{tab_id}": {
            "get": {
                "summary": "Get tab metadata (preview)",
                "parameters": [
                    {"name": "tab_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Tab metadata"},
                    "404": {"description": "Tab not found"},
                },
            }
        },
        "/stats": {
            "get": {
                "summary": "Database statistics",
                "responses": {"200": {"description": "Stats object"}},
            }
        },
        "/artists": {
            "get": {
                "summary": "Paginated artist list",
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Filter artists by name"},
                ],
                "responses": {"200": {"description": "Artist list"}},
            }
        },
        "/random": {
            "get": {
                "summary": "Random tabs for discovery",
                "parameters": [
                    {"name": "count", "in": "query", "schema": {"type": "integer", "default": 5, "minimum": 1, "maximum": 50}},
                ],
                "responses": {"200": {"description": "Random tabs"}},
            }
        },
        "/recommendations": {
            "get": {
                "summary": "Recommended tabs based on favorite artists",
                "parameters": [
                    {"name": "artists", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Comma-separated artist names"},
                    {"name": "exclude", "in": "query", "schema": {"type": "string"}, "description": "Comma-separated tab IDs to exclude"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50}},
                ],
                "responses": {"200": {"description": "Recommended tabs"}},
            }
        },
        "/search/live": {
            "get": {
                "summary": "Live search across multiple sources",
                "description": "Searches local database and external tab sites (Songsterr, Ultimate Guitar) in parallel, merging and deduplicating results.",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string", "minLength": 2}, "description": "Search query"},
                    {"name": "sources", "in": "query", "schema": {"type": "string"}, "description": "Comma-separated source names: local, songsterr, ultimate_guitar (default: all)"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 100}},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1, "minimum": 1}},
                ],
                "responses": {
                    "200": {"description": "Live search results with per-source status"},
                    "400": {"description": "Invalid query or source name"},
                },
            }
        },
        "/sources": {
            "get": {
                "summary": "Available sources with tab counts",
                "responses": {"200": {"description": "Source list"}},
            }
        },
        "/metadata/artist/{artist_name}": {
            "get": {
                "summary": "Get artist metadata (image, bio, tags)",
                "parameters": [
                    {"name": "artist_name", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {"200": {"description": "Artist metadata"}},
            }
        },
        "/metadata/artwork": {
            "get": {
                "summary": "Get song album artwork",
                "parameters": [
                    {"name": "artist", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "title", "in": "query", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {"200": {"description": "Artwork URL"}},
            }
        },
        "/youtube/search": {
            "get": {
                "summary": "Search YouTube for videos",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 5}},
                ],
                "responses": {"200": {"description": "YouTube search results"}},
            }
        },
    },
}


# ============================================================
# Route registration helper: register on both /api/ and /api/v1/
# ============================================================
def _register_routes():
    """Register all routes under both /api and /api/v1 prefixes."""

    # --- Health / Hello ---
    @app.route('/api/health', methods=['GET'])
    @app.route('/api/v1/health', methods=['GET'])
    def health():
        """Health check endpoint"""
        uptime = time.time() - startup_time
        return HealthResponse(
            status="ok",
            uptime=uptime,
            timestamp=int(time.time() * 1000)
        ).model_dump(by_alias=True)

    @app.route('/api/hello', methods=['GET'])
    @app.route('/api/v1/hello', methods=['GET'])
    def hello():
        """Hello endpoint"""
        return HelloResponse(
            message="Hello API!"
        ).model_dump(by_alias=True)

    # --- Search ---
    @app.route('/api/search', methods=['GET'])
    @app.route('/api/v1/search', methods=['GET'])
    def search():
        """Search endpoint"""
        return search_controller.search()

    # --- Autocomplete ---
    @app.route('/api/autocomplete', methods=['GET'])
    @app.route('/api/v1/autocomplete', methods=['GET'])
    def autocomplete():
        """Autocomplete endpoint"""
        return autocomplete_controller.autocomplete()

    # --- Download ---
    @app.route('/api/download/<tab_id>', methods=['GET'])
    @app.route('/api/v1/download/<tab_id>', methods=['GET'])
    def download(tab_id):
        """Download endpoint"""
        return download_controller.download(tab_id)

    # --- New endpoints ---
    @app.route('/api/tab/<tab_id>', methods=['GET'])
    @app.route('/api/v1/tab/<tab_id>', methods=['GET'])
    def tab_detail(tab_id):
        """Tab metadata endpoint (preview cards)"""
        return catalog_controller.get_tab(tab_id)

    @app.route('/api/stats', methods=['GET'])
    @app.route('/api/v1/stats', methods=['GET'])
    def stats():
        """Database stats endpoint"""
        return catalog_controller.stats()

    @app.route('/api/artists', methods=['GET'])
    @app.route('/api/v1/artists', methods=['GET'])
    def artists():
        """Artists list endpoint"""
        return catalog_controller.artists()

    @app.route('/api/random', methods=['GET'])
    @app.route('/api/v1/random', methods=['GET'])
    def random_tabs():
        """Random tabs endpoint"""
        return catalog_controller.random_tabs()

    @app.route('/api/recommendations', methods=['GET'])
    @app.route('/api/v1/recommendations', methods=['GET'])
    def recommendations():
        """Recommendations endpoint"""
        return catalog_controller.recommendations()

    # --- Live Search ---
    @app.route('/api/search/live', methods=['GET'])
    @app.route('/api/v1/search/live', methods=['GET'])
    def live_search():
        """Live search endpoint across multiple sources"""
        return live_search_controller.search()

    @app.route('/api/sources', methods=['GET'])
    @app.route('/api/v1/sources', methods=['GET'])
    def sources():
        """Sources list endpoint"""
        return catalog_controller.sources()

    # --- Metadata ---
    @app.route('/api/metadata/artist/<path:artist_name>', methods=['GET'])
    @app.route('/api/v1/metadata/artist/<path:artist_name>', methods=['GET'])
    def metadata_artist(artist_name):
        """Artist metadata endpoint"""
        return metadata_controller.artist_info(artist_name)

    @app.route('/api/metadata/artwork', methods=['GET'])
    @app.route('/api/v1/metadata/artwork', methods=['GET'])
    def metadata_artwork():
        """Song artwork endpoint"""
        return metadata_controller.song_artwork()

    @app.route('/api/metadata/artwork/batch', methods=['POST'])
    @app.route('/api/v1/metadata/artwork/batch', methods=['POST'])
    def metadata_artwork_batch():
        """Batch artwork endpoint"""
        return metadata_controller.batch_artwork()

    @app.route('/api/youtube/search', methods=['GET'])
    @app.route('/api/v1/youtube/search', methods=['GET'])
    def youtube_search():
        """YouTube search endpoint"""
        return metadata_controller.youtube_search()

    # --- OpenAPI spec endpoint ---
    @app.route('/api/docs', methods=['GET'])
    @app.route('/api/v1/docs', methods=['GET'])
    def openapi_docs():
        """Return OpenAPI specification"""
        return jsonify(OPENAPI_SPEC)


_register_routes()


@app.errorhandler(404)
def not_found(e):
    """Handle unmapped routes."""
    request_id = getattr(g, 'request_id', None)
    logger.debug("404 for path: %s (request_id=%s)", request.path, request_id)
    return jsonify({"error": "The requested resource was not found.", "requestId": request_id}), 404


# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('NODE_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
