
import logging
from urllib.parse import urlparse, unquote
from flask import g, jsonify, Response, stream_with_context
from api.services.download_service import DownloadService

logger = logging.getLogger(__name__)


class DownloadController:
    def __init__(self):
        self.download_service = DownloadService()

    def download(self, tab_id: str):
        """Handle download requests"""
        try:
            download_url = self.download_service.get_tab_download_url(tab_id)

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
