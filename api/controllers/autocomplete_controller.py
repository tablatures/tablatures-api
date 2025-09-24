from flask import request, jsonify
from api.services.autocomplete_service import AutocompleteService

class AutocompleteController:
    def __init__(self):
        self.autocomplete_service = AutocompleteService()
    
    def autocomplete(self):
        """Handle autocomplete requests"""
        try:
            query = request.args.get('q', '')
            limit = min(int(request.args.get('limit', 10)), 50)
            
            if not query or len(query.strip()) < 1:
                return jsonify({"error": 'Query parameter "q" is required (min 1 char)'}), 400
            
            results = self.autocomplete_service.get_suggestions(query, limit).model_dump(by_alias=True)
            
            response = jsonify(results)
            response.headers['Cache-Control'] = 's-maxage=600, stale-while-revalidate'
            return response
            
        except Exception as e:
            print(f"Autocomplete failed: {e}")
            return jsonify({"error": "Internal server error"}), 500
