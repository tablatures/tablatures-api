
import os
import time
from flask import Flask
from flask_cors import CORS
from api.models import HealthResponse, HelloResponse
from api.controllers.search_controller import SearchController
from api.controllers.autocomplete_controller import AutocompleteController  
from api.controllers.download_controller import DownloadController

app = Flask(__name__)
CORS(app)

search_controller = SearchController()
autocomplete_controller = AutocompleteController()
download_controller = DownloadController()

startup_time = time.time()

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    uptime = time.time() - startup_time
    
    return HealthResponse(
        status="ok",
        uptime=uptime,
        timestamp=int(time.time() * 1000)
    ).model_dump(by_alias=True)

@app.route('/api/hello', methods=['GET'])  
def hello():
    """Hello endpoint"""
    return HelloResponse(
        message="Hello API!"
    ).model_dump(by_alias=True)

@app.route('/api/search', methods=['GET'])
def search():
    """Search endpoint"""
    return search_controller.search()

@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    """Autocomplete endpoint"""
    return autocomplete_controller.autocomplete()

@app.route('/api/download/<tab_id>', methods=['GET'])
def download(tab_id):
    """Download endpoint"""
    return download_controller.download(tab_id)

# For local development
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    debug = os.environ.get('NODE_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)