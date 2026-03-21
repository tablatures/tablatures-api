import logging
from flask import jsonify, request
from api.services.metadata_service import get_artist_info, get_song_artwork, search_youtube

logger = logging.getLogger(__name__)


class MetadataController:
    def artist_info(self, artist_name: str):
        """Get artist metadata (image, bio, tags)."""
        if not artist_name or len(artist_name.strip()) < 1:
            return jsonify({"error": "Artist name required"}), 400

        info = get_artist_info(artist_name.strip())
        return jsonify(info)

    def song_artwork(self):
        """Get album artwork for a song."""
        artist = request.args.get("artist", "").strip()
        title = request.args.get("title", "").strip()

        if not artist or not title:
            return jsonify({"error": "Both artist and title parameters required"}), 400

        url = get_song_artwork(artist, title)
        return jsonify({"artworkUrl": url})

    def youtube_search(self):
        """Search YouTube for videos."""
        q = request.args.get("q", "").strip()
        limit = min(int(request.args.get("limit", 5)), 10)

        if not q or len(q) < 2:
            return jsonify({"error": "Query too short"}), 400

        results = search_youtube(q, limit)
        return jsonify({"results": results})
