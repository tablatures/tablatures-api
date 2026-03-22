import logging
from flask import jsonify, request
from api.services.metadata_service import get_artist_info, get_song_artwork, search_youtube, get_artworks_batch
from api.services.artist_parser import parse_artists

logger = logging.getLogger(__name__)


class MetadataController:
    def artist_info(self, artist_name: str):
        """Get artist metadata (image, bio, tags)."""
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

        return jsonify(info)

    def song_artwork(self):
        """Get album artwork for a song."""
        artist = request.args.get("artist", "").strip()
        title = request.args.get("title", "").strip()

        if not artist or not title:
            return jsonify({"error": "Both artist and title parameters required"}), 400

        url = get_song_artwork(artist, title)
        return jsonify({"artworkUrl": url})

    def batch_artwork(self):
        """POST endpoint: get artwork for multiple items at once."""
        items = request.get_json(silent=True) or []
        if not isinstance(items, list) or len(items) > 50:
            return jsonify({"error": "Expected array of max 50 items"}), 400
        results = get_artworks_batch(items)
        return jsonify(results)

    def youtube_search(self):
        """Search YouTube for videos."""
        q = request.args.get("q", "").strip()
        limit = min(int(request.args.get("limit", 5)), 10)

        if not q or len(q) < 2:
            return jsonify({"error": "Query too short"}), 400

        results = search_youtube(q, limit)
        return jsonify({"results": results})
