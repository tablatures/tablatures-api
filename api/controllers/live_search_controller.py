import logging
from flask import g, request, jsonify
from api.services.live_search_service import LiveSearchService, VALID_SOURCE_NAMES
from api.utils import sanitize_string, parse_pagination_params

logger = logging.getLogger(__name__)


class LiveSearchController:
    def __init__(self):
        self.live_search_service = LiveSearchService()

    def search(self):
        """Handle live search requests across multiple sources."""
        try:
            query = sanitize_string(request.args.get('q', ''))
            page, limit = parse_pagination_params(default_limit=50, max_limit=100)

            if not query or len(query.strip()) < 2:
                return jsonify({
                    "error": 'Query parameter "q" is required (min 2 chars)',
                    "requestId": getattr(g, 'request_id', None),
                }), 400

            # Parse sources parameter
            sources_param = request.args.get('sources', '')
            if sources_param:
                requested = [s.strip().lower() for s in sources_param.split(',') if s.strip()]
                invalid = [s for s in requested if s not in VALID_SOURCE_NAMES]
                if invalid:
                    return jsonify({
                        "error": f"Invalid source(s): {', '.join(invalid)}. Valid sources: {', '.join(sorted(VALID_SOURCE_NAMES))}",
                        "requestId": getattr(g, 'request_id', None),
                    }), 400
                sources = requested
            else:
                sources = None  # all sources

            result = self.live_search_service.search(
                query=query,
                sources=sources,
                limit=limit,
                page=page,
            )

            response = jsonify(result)
            response.headers['Cache-Control'] = 's-maxage=900, stale-while-revalidate'
            return response

        except Exception as e:
            logger.error(
                "Live search failed for query='%s' (request_id=%s): %s",
                request.args.get('q', ''),
                getattr(g, 'request_id', None),
                e,
                exc_info=True,
            )
            return jsonify({
                "error": "Internal server error",
                "requestId": getattr(g, 'request_id', None),
            }), 500
