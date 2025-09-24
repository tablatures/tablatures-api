
from flask import jsonify, Response, stream_with_context
from api.services.download_service import DownloadService

class DownloadController:
    def __init__(self):
        self.download_service = DownloadService()
    
    def download(self, tab_id: str):
        """Handle download requests"""
        try:
            download_url = self.download_service.get_tab_download_url(tab_id)
            
            if not download_url:
                return jsonify({"error": "Tab not found"}), 404
            
            def generate():
                try:
                    for chunk in self.download_service.stream_file(download_url):
                        yield chunk
                except Exception as e:
                    print(f"Streaming error: {e}")
                    yield b""  # End stream on error
            
            return Response(
                stream_with_context(generate()),
                content_type='application/octet-stream'
            )
            
        except Exception as e:
            print(f"Download failed: {e}")
            return jsonify({"error": "Internal server error"}), 500