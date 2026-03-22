import logging
from flask import jsonify, request, make_response
from api.services.metadata_service import get_artist_info, get_song_artwork, search_youtube, get_artworks_batch
from api.services.artist_parser import parse_artists

logger = logging.getLogger(__name__)

# Cache durations for browser HTTP caching
_ARTIST_CACHE_SECS = 86400 * 7   # 7 days - artist info rarely changes
_ARTWORK_CACHE_SECS = 86400 * 7  # 7 days - artwork URLs are stable
_YOUTUBE_CACHE_SECS = 3600       # 1 hour - YouTube results change more often


def _cached_json(data, max_age: int):
    """Return JSON response with Cache-Control header for browser caching."""
    resp = make_response(jsonify(data))
    resp.headers['Cache-Control'] = f'public, max-age={max_age}'
    return resp


class MetadataController:
    def artist_info(self, artist_name: str):
        """Get artist metadata (image, bio, tags). Cached 7 days in browser."""
        if not artist_name or len(artist_name.strip()) < 1:
            return jsonify({"error": "Artist name required"}), 400

        info = get_artist_info(artist_name.strip())

        # If no image found, try splitting compound artist names
        if not info.get("image"):
            parts = parse_artists(artist_name.strip())
            if len(parts) > 1:
                for part in parts:
                    part_info = get_artist_info(part)
                    if part_info.get("image"):
                        info["image"] = part_info["image"]
                        if not info.get("bio"):
                            info["bio"] = part_info.get("bio")
                        break

        return _cached_json(info, _ARTIST_CACHE_SECS)

    def song_artwork(self):
        """Get album artwork for a song. Cached 7 days in browser."""
        artist = request.args.get("artist", "").strip()
        title = request.args.get("title", "").strip()

        if not artist or not title:
            return jsonify({"error": "Both artist and title parameters required"}), 400

        url = get_song_artwork(artist, title)
        return _cached_json({"artworkUrl": url}, _ARTWORK_CACHE_SECS)

    def batch_artwork(self):
        """POST endpoint: get artwork for multiple items at once. Cached 7 days."""
        items = request.get_json(silent=True) or []
        if not isinstance(items, list) or len(items) > 50:
            return jsonify({"error": "Expected array of max 50 items"}), 400
        results = get_artworks_batch(items)
        return _cached_json(results, _ARTWORK_CACHE_SECS)

    def youtube_search(self):
        """Search YouTube for videos. Cached 1 hour."""
        q = request.args.get("q", "").strip()
        limit = min(int(request.args.get("limit", 5)), 10)

        if not q or len(q) < 2:
            return jsonify({"error": "Query too short"}), 400

        results = search_youtube(q, limit)
        return _cached_json({"results": results}, _YOUTUBE_CACHE_SECS)
