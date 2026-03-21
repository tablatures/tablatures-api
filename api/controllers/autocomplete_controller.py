
import logging
from flask import g, request, jsonify
from api.services.autocomplete_service import AutocompleteService
from api.utils import sanitize_string

logger = logging.getLogger(__name__)


class AutocompleteController:
    def __init__(self):
        self.autocomplete_service = AutocompleteService()

    def autocomplete(self):
        """Handle autocomplete requests"""
        try:
            query = sanitize_string(request.args.get('q', ''))
            try:
                limit = min(int(request.args.get('limit', 10)), 50)
                limit = max(limit, 1)
            except (ValueError, TypeError):
                limit = 10

            if not query or len(query.strip()) < 1:
                return jsonify({"error": 'Query parameter "q" is required (min 1 char)', "requestId": getattr(g, 'request_id', None)}), 400

            results = self.autocomplete_service.get_suggestions(query, limit).model_dump(by_alias=True)

            response = jsonify(results)
            response.headers['Cache-Control'] = 's-maxage=600, stale-while-revalidate'
            return response

        except Exception as e:
            logger.error("Autocomplete failed (request_id=%s): %s", getattr(g, 'request_id', None), e)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500
