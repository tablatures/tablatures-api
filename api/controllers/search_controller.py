
import logging
from flask import g, request, jsonify
from api.services.search_service import SearchService
from api.utils import sanitize_string, parse_pagination_params

logger = logging.getLogger(__name__)

# Allowed sort values
VALID_SORT_OPTIONS = {"relevance", "alphabetical", "newest"}


class SearchController:
    def __init__(self):
        self.search_service = SearchService()

    def search(self):
        """Handle search requests"""
        try:
            query = sanitize_string(request.args.get('q', ''))
            page, limit = parse_pagination_params(default_limit=50, max_limit=100)

            if not query or len(query.strip()) < 2:
                return jsonify({"error": 'Query parameter "q" is required (min 2 chars)', "requestId": getattr(g, 'request_id', None)}), 400

            # New filter parameters
            source_filter = request.args.get('source')
            if source_filter:
                source_filter = sanitize_string(source_filter, max_length=50)
            artist_filter = request.args.get('artist')
            if artist_filter:
                artist_filter = sanitize_string(artist_filter, max_length=100)
            type_filter = request.args.get('type')
            if type_filter:
                type_filter = sanitize_string(type_filter, max_length=50)

            # Sort parameter
            sort = request.args.get('sort', 'relevance').lower()
            if sort not in VALID_SORT_OPTIONS:
                sort = 'relevance'

            results = self.search_service.search_tabs(
                query, limit, page,
                source_filter=source_filter,
                artist_filter=artist_filter,
                type_filter=type_filter,
                sort=sort,
            ).model_dump(by_alias=True)

            response = jsonify(results)
            response.headers['Cache-Control'] = 's-maxage=3600, stale-while-revalidate'
            return response

        except Exception as e:
            logger.error("Search failed for query='%s' (request_id=%s): %s", request.args.get('q', ''), getattr(g, 'request_id', None), e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500
