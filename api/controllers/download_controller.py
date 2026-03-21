
import logging
import requests
from urllib.parse import urlparse, unquote
from flask import g, jsonify, Response, stream_with_context
from api.services.download_service import DownloadService

logger = logging.getLogger(__name__)


def _resolve_external_download_url(tab_id: str):
    """Resolve download URL for external source tabs (songsterr:ID, ug:ID).

    For Songsterr: fetches the latest revision, then gets the GP source URL.
    The source URL requires Origin: https://www.songsterr.com header.
    """
    if tab_id.startswith("songsterr:"):
        song_id = tab_id.split(":", 1)[1]
        if not song_id:
            return None
        try:
            # Step 1: Get revisions for this song
            rev_resp = requests.get(
                f"https://www.songsterr.com/api/meta/{song_id}/revisions",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if not rev_resp.ok:
                return None
            revisions = rev_resp.json()
            if not revisions:
                return None

            # Step 2: Try revisions until we find one with a source URL
            # Recent editor-created revisions may not have source, older imported ones do
            for rev in revisions[:10]:
                revision_id = rev.get("revisionId")
                if not revision_id:
                    continue
                detail_resp = requests.get(
                    f"https://www.songsterr.com/api/revision/{revision_id}",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=5,
                )
                if not detail_resp.ok:
                    continue
                detail = detail_resp.json()
                source_url = detail.get("source")
                if source_url and "gp.songsterr.com" in source_url:
                    return source_url

        except Exception as e:
            logger.warning("Failed to resolve Songsterr download for %s: %s", tab_id, e)
        return None
    return None


class DownloadController:
    def __init__(self):
        self.download_service = DownloadService()

    def download(self, tab_id: str):
        """Handle download requests"""
        try:
            # Try local DB first
            download_url = self.download_service.get_tab_download_url(tab_id)

            # Fallback: resolve external source URLs
            if not download_url:
                download_url = _resolve_external_download_url(tab_id)

            if not download_url:
                return jsonify({"error": "Tab not found", "requestId": getattr(g, 'request_id', None)}), 404

            def generate():
                try:
                    for chunk in self.download_service.stream_file(download_url):
                        yield chunk
                except Exception as e:
                    logger.error("Streaming error for tab_id=%s url=%s: %s", tab_id, download_url, e)
                    yield b""  # End stream on error

            # Derive filename from URL path
            parsed_path = urlparse(download_url).path
            filename = unquote(parsed_path.rsplit('/', 1)[-1]) or f"{tab_id}.gp"

            return Response(
                stream_with_context(generate()),
                content_type='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                },
            )

        except Exception as e:
            logger.error("Download failed for tab_id=%s (request_id=%s): %s", tab_id, getattr(g, 'request_id', None), e, exc_info=True)
            return jsonify({"error": "Internal server error", "requestId": getattr(g, 'request_id', None)}), 500
