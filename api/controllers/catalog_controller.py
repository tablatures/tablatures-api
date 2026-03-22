
import logging
from flask import g, request, jsonify
from api.services.catalog_service import CatalogService
from api.utils import sanitize_string, parse_pagination_params

logger = logging.getLogger(__name__)


class CatalogController:
    def __init__(self):
        self.catalog_service = CatalogService()

    def get_tab(self, tab_id: str):
        """Return tab metadata without download URL."""
        try:
            tab_id = sanitize_string(tab_id, max_length=100)
            result = self.catalog_service.get_tab_detail(tab_id)
            if result is None:
                return jsonify({"error": "Tab not found", "requestId": getattr(g, 'request_id', None)}), 404
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 's-maxage=3600, stale-while-revalidate'
            return response
        except Exception as e:
            logger.error("Get tab failed for tab_id=%s: %s", tab_id, e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500

    def stats(self):
        """Return database statistics."""
        try:
            result = self.catalog_service.get_stats()
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 's-maxage=600, stale-while-revalidate'
            return response
        except Exception as e:
            logger.error("Stats endpoint failed: %s", e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500

    def artists(self):
        """Return paginated artist list."""
        try:
            page, limit = parse_pagination_params(default_limit=50, max_limit=200)
            q = request.args.get('q')
            if q:
                q = sanitize_string(q, max_length=100)

            result = self.catalog_service.get_artists(page=page, limit=limit, q=q)
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 's-maxage=600, stale-while-revalidate'
            return response
        except Exception as e:
            logger.error("Artists endpoint failed: %s", e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500

    def random_tabs(self):
        """Return random tabs."""
        try:
            try:
                count = min(max(int(request.args.get('count', 5)), 1), 50)
            except (ValueError, TypeError):
                count = 5

            result = self.catalog_service.get_random_tabs(count=count)
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 'no-cache'
            return response
        except Exception as e:
            logger.error("Random tabs endpoint failed: %s", e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500

    def recommendations(self):
        """Return recommended tabs based on favorite artists."""
        try:
            # Support both ?artists=a,b,c (old format) and ?artists=a&artists=b (new format)
            artists_list = request.args.getlist('artists')
            artists = []
            for param in artists_list:
                # Handle comma-separated values within each parameter for backward compatibility
                for a in param.split(','):
                    a = a.strip()
                    if a:
                        artists.append(sanitize_string(a, max_length=100))

            if not artists:
                return jsonify({"error": "Missing required parameter: artists", "requestId": getattr(g, 'request_id', None)}), 400

            exclude_param = request.args.get('exclude', '')
            exclude = set()
            if exclude_param:
                exclude = {sanitize_string(e.strip(), max_length=100) for e in exclude_param.split(',') if e.strip()}

            try:
                limit = min(max(int(request.args.get('limit', 20)), 1), 50)
            except (ValueError, TypeError):
                limit = 20

            result = self.catalog_service.get_recommendations(artists=artists, exclude=exclude, limit=limit)
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 's-maxage=300, stale-while-revalidate'
            return response
        except Exception as e:
            logger.error("Recommendations endpoint failed: %s", e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500

    def sources(self):
        """Return available sources with tab counts."""
        try:
            result = self.catalog_service.get_sources()
            response = jsonify(result.model_dump(by_alias=True))
            response.headers['Cache-Control'] = 's-maxage=600, stale-while-revalidate'
            return response
        except Exception as e:
            logger.error("Sources endpoint failed: %s", e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500
