
from flask import request, jsonify
from api.services.search_service import SearchService

class SearchController:
    def __init__(self):
        self.search_service = SearchService()
    
    def search(self):
        """Handle search requests"""
        try:
            query = request.args.get('q', '')
            limit = min(int(request.args.get('limit', 50)), 100)
            page = max(int(request.args.get('page', 1)), 1)
            
            if not query or len(query.strip()) < 2:
                return jsonify({"error": 'Query parameter "q" is required (min 2 chars)'}), 400
            
            results = self.search_service.search_tabs(query, limit, page).model_dump(by_alias=True)
            
            # Convert Pydantic models to dict for JSON serialization
            results_dict = {
                "results": results["results"],
                "total": results["total"],
                "page": results["page"], 
                "limit": results["limit"],
                "totalPages": results["totalPages"]
            }
            
            response = jsonify(results_dict)
            response.headers['Cache-Control'] = 's-maxage=3600, stale-while-revalidate'
            return response
            
        except Exception as e:
            print(f"Search failed: {e}")
            return jsonify({"error": "Internal server error"}), 500