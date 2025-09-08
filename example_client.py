#!/usr/bin/env python3
"""
Example client for the AI Search Suggestions API
Demonstrates how to integrate with the API from external applications
"""

import requests
import json
from typing import Dict, List, Optional

class AISuggestionClient:
    def __init__(self, base_url: str = "http://127.0.0.1:5000", api_key: str = "demo-key", ab_variant: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.ab_variant = ab_variant
    
    def _headers(self, with_json: bool = True) -> Dict[str, str]:
        headers = {"X-API-Key": self.api_key}
        if with_json:
            headers["Content-Type"] = "application/json"
        if self.ab_variant:
            headers["X-AB-Variant"] = self.ab_variant
        return headers
    
    def get_suggestions(self, query: str, user_id: str = "demo_user", 
                       site_data: Optional[Dict] = None, 
                       user_location: Optional[str] = None,
                       user_lat: Optional[float] = None,
                       user_lon: Optional[float] = None,
                       search_history: Optional[List[str]] = None,
                       debug: bool = False) -> Dict:
        """
        Get AI-powered search suggestions
        
        Args:
            query: The search query
            user_id: Unique user identifier
            site_data: Website data (categories, members, etc.)
            user_location: User's location as text
            user_lat: User's latitude
            user_lon: User's longitude
            search_history: User's previous search queries
            
        Returns:
            API response with suggestions
        """
        payload = {
            "current_query": query,
            "user_id": user_id,
            "user_search_history": search_history or [],
            "user_location": user_location,
            "user_latitude": user_lat,
            "user_longitude": user_lon,
            "site_data": site_data or {},
            "debug": debug
        }
        
        try:
            response = requests.post(f"{self.base_url}/suggest", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def submit_feedback(self, user_id: str, query: str, selected_suggestion: str,
                       success_rating: int = 5, location: Optional[str] = None) -> Dict:
        """
        Submit feedback on suggestions for learning
        
        Args:
            user_id: User identifier
            query: Original search query
            selected_suggestion: The suggestion the user selected
            success_rating: Rating from 1-5
            location: User's location
            
        Returns:
            API response
        """
        payload = {
            "user_id": user_id,
            "query": query,
            "selected_suggestion": selected_suggestion,
            "success_rating": success_rating,
            "location": location
        }
        
        try:
            response = requests.post(f"{self.base_url}/feedback", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def add_manual_data(self, data_type: str, content: Dict, added_by: str = "admin") -> Dict:
        """
        Add manual data to the system
        
        Args:
            data_type: Type of data (category, member, profession, location)
            content: Data content
            added_by: Who added the data
            
        Returns:
            API response
        """
        payload = {
            "type": data_type,
            "content": content,
            "added_by": added_by
        }
        
        try:
            response = requests.post(f"{self.base_url}/data", json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def get_analytics(self) -> Dict:
        """Get system analytics"""
        try:
            response = requests.get(f"{self.base_url}/analytics", headers=self._headers(with_json=False))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def health_check(self) -> Dict:
        """Check API health"""
        try:
            response = requests.get(f"{self.base_url}/")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}


def demo_usage():
    """Demonstrate the API usage"""
    client = AISuggestionClient(api_key="demo-key", ab_variant="A")
    
    print("=== AI Search Suggestions API Demo ===\n")
    
    # Health check
    print("1. Health Check:")
    health = client.health_check()
    print(f"   Status: {health.get('status', 'error')}")
    print(f"   Service: {health.get('service', 'unknown')}\n")
    
    # Sample website data
    sample_site_data = {
        "categories": [
            {
                "top_category": "Healthcare",
                "sub_category": "Medical",
                "sub_sub_category": "General Practice"
            },
            {
                "top_category": "Home Services",
                "sub_category": "Plumbing"
            }
        ],
        "members": [
            {
                "name": "Dr. John Smith",
                "tags": "family doctor, general practice, pediatrics",
                "location": "New York, NY",
                "reviews": "Excellent family doctor with 20 years experience",
                "rating": 4.8
            },
            {
                "name": "ABC Plumbing Services",
                "tags": "emergency, residential, commercial",
                "location": "New York, NY",
                "reviews": "Reliable 24/7 plumbing services",
                "rating": 4.6
            }
        ]
    }
    
    # Get suggestions
    print("2. Getting Suggestions:")
    suggestions = client.get_suggestions(
        query="doctor near me",
        user_id="demo_user_123",
        site_data=sample_site_data,
        user_location="New York",
        user_lat=40.7128,
        user_lon=-74.0060,
        search_history=["dentist", "plumber"],
        debug=True
    )
    
    if "error" not in suggestions:
        print(f"   Query: {suggestions['original_query']}")
        print("   Suggestions:")
        for i, suggestion in enumerate(suggestions['suggestions'], 1):
            print(f"   {i}. {suggestion}")
    else:
        print(f"   Error: {suggestions['error']}")
    
    print()
    
    # Submit feedback
    print("3. Submitting Feedback:")
    if "error" not in suggestions and suggestions.get('suggestions'):
        feedback = client.submit_feedback(
            user_id="demo_user_123",
            query="doctor near me",
            selected_suggestion=suggestions['suggestions'][0],
            success_rating=5,
            location="New York"
        )
        print(f"   Feedback Status: {feedback.get('status', 'error')}")
    else:
        print("   Skipping feedback (no suggestions available)")
    
    print()
    
    # Add manual data
    print("4. Adding Manual Data:")
    manual_data = client.add_manual_data(
        data_type="member",
        content={
            "name": "Dr. Jane Doe",
            "location": "Los Angeles, CA",
            "rating": 4.9,
            "specialty": "Cardiology"
        },
        added_by="demo_admin"
    )
    print(f"   Data Addition Status: {manual_data.get('status', 'error')}")
    
    print()
    
    # Get analytics
    print("5. System Analytics:")
    analytics = client.get_analytics()
    if "error" not in analytics:
        stats = analytics.get('statistics', {})
        print(f"   Total Searches: {stats.get('total_searches', 0)}")
        print(f"   Unique Users: {stats.get('unique_users', 0)}")
        print(f"   Average Rating: {stats.get('average_rating', 0)}")
        
        top_queries = analytics.get('top_queries', [])
        if top_queries:
            print("   Top Queries:")
            for query in top_queries[:3]:
                print(f"     - {query['query']} ({query['frequency']} times)")
    else:
        print(f"   Error: {analytics['error']}")


if __name__ == "__main__":
    demo_usage()
