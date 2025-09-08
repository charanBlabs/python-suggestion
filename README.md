# AI Search Suggestions API

An intelligent search suggestion microservice for Brilliant Directories-style sites. It combines semantic embeddings, BM25, personalization, geo-awareness, business rules, and self-learning to deliver high-quality suggestions. Now includes API key auth, rate limiting, member result cards, debug explainability, event tracking, batch import, analytics filters/CSV, and caching.

## Quick Start

1. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

2. Set environment variables (optional but recommended)
```bash
# Comma-separated list of allowed API keys
set API_KEYS=demo-key
# Requests per minute per API key
set RATE_LIMIT_PER_MINUTE=120
# SQLite database file
set DB_PATH=ai_suggestions.db
# Embedding model
set EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
# Suggestion cache TTL (seconds)
set SUGGESTION_CACHE_TTL_SECONDS=300
```

3. Run the server
```bash
python app.py
```
API base URL: `http://127.0.0.1:5000`

4. Import the Postman collection
- Open `AI_Search_Suggestions_API.postman_collection.json` in Postman
- Set collection variables:
  - `base_url` = `http://127.0.0.1:5000`
  - `api_key` = `demo-key`

## Auth and Headers
- All endpoints (except `GET /`) require the header:
  - `X-API-Key: <your key>`
- Optional A/B header on `/suggest`:
  - `X-AB-Variant: A` (or any label)

## Core Endpoint: Get Suggestions

POST `/suggest`

Request body (example):
```json
{
  "current_query": "doctor near me",
  "user_id": "user123",
  "user_search_history": ["dentist", "plumber"],
  "user_location": "New York, NY",
  "user_latitude": 40.7128,
  "user_longitude": -74.0060,
  "debug": true,
  "site_data": {
    "settings": { "radius_km": 25 },
    "categories": [
      { "top_category": "Healthcare", "sub_category": "Medical", "sub_sub_category": "General Practice" }
    ],
    "members": [
      {
        "id": 101,
        "name": "Dr. John Smith",
        "tags": "family doctor, general practice, pediatrics",
        "location": "New York, NY",
        "rating": 4.8,
        "profile_url": "https://example.com/members/101",
        "thumbnail_url": "https://picsum.photos/seed/101/200",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "featured": true,
        "plan_level": "premium",
        "priority_score": 2,
        "promo_badge": "10% off",
        "hours": { "mon": [["09:00","17:00"]] }
      }
    ]
  }
}
```

Response (example):
```json
{
  "original_query": "doctor near me",
  "suggestions": ["Book Dr. John Smith in New York", "Top-rated Healthcare near you", "Best Medical in New York", "Trusted Dr. John Smith nearby", "Reserve Healthcare today"],
  "cards": [
    {
      "title": "Dr. John Smith",
      "member_id": 101,
      "profile_url": "https://example.com/members/101",
      "thumbnail_url": "https://picsum.photos/seed/101/200",
      "rating": 4.8,
      "location": "New York, NY",
      "distance_km": 0.0,
      "promo_badge": "10% off",
      "featured": true
    }
  ],
  "user_id": "user123",
  "timestamp": "2025-01-01T12:00:00Z",
  "debug": {
    "intent": "hire",
    "city": "New York",
    "top_candidates": [ { "text": "Dr. John Smith", "type": "member", "score": 1.2345, "distance_km": 0.0 } ]
  }
}
```

Notes
- Ranking: semantic + BM25 + boosts (history, rating, geo proximity/radius, featured/plan/priority, open-now, promotions), plus learned preferences and negative feedback suppression.
- Synonyms/ontology: extend via `/data` type `synonym`.
- Cold-start: falls back to popular categories/professions if no candidates.

## Feedback (Learning)

POST `/feedback`
```json
{ "user_id": "user123", "query": "doctor near me", "selected_suggestion": "Top-rated Healthcare near you", "success_rating": 5, "location": "New York" }
```
Response: `{ "status": "feedback_received" }`

## Manual Data

POST `/data`
- Valid `type`: `category`, `member`, `profession`, `location`, `synonym`, `blacklist`, `whitelist`
```json
{ "type": "member", "content": { "name": "Dr. Jane Doe", "location": "Los Angeles, CA", "rating": 4.9 }, "added_by": "admin" }
```

GET `/data?type=member`
- Returns stored manual data (filtered by type when provided).

## Batch Import

POST `/batch_import`
```json
{
  "added_by": "postman",
  "items": [
    { "type": "member", "content": { "name": "Midtown Plumbing", "location": "New York, NY", "rating": 4.7 } },
    { "type": "category", "content": { "name": "Legal Services" } }
  ]
}
```
Response: `{ "status": "ok", "imported": 2, "failed": 0 }`

## Event Tracking

POST `/event`
```json
{ "user_id": "user123", "event_type": "member_click", "payload": { "member_id": 101, "profile_url": "https://example.com/members/101" } }
```
Response: `{ "status": "ok" }`

## Analytics

GET `/analytics?start=2024-01-01&end=2030-01-01`
- Returns summary stats, top queries/suggestions, event counts, learning patterns.

GET `/analytics?format=csv`
- Returns CSV of top queries.

## Health

GET `/`
- Returns `{ "status": "ok", "service": "bd-suggest-extended", "model": "..." }`

## Using the Example Client

- The client now sends `X-API-Key` and optional `X-AB-Variant` headers.
```bash
python example_client.py
```
- Adjust base URL and API key in `AISuggestionClient(base_url, api_key, ab_variant)` as needed.

## Load Testing (Robustness)

A simple concurrent load test script is included.

Run:
```bash
python load_test.py --concurrency 20 --requests 200 --base-url http://127.0.0.1:5000 --api-key demo-key
```
Output includes throughput, latency (mean/p50/min/max), and error breakdown. If you hit 429 (Too Many Requests), increase `RATE_LIMIT_PER_MINUTE` or use multiple API keys.

## Configuration

Environment variables:
- `PORT` (default: 5000)
- `DB_PATH` (default: ai_suggestions.db)
- `EMBEDDING_MODEL` (default: sentence-transformers/all-MiniLM-L6-v2)
- `API_KEYS` (default: demo-key)
- `RATE_LIMIT_PER_MINUTE` (default: 120)
- `SUGGESTION_CACHE_TTL_SECONDS` (default: 300)

## Implementation Notes
- Model loading is cached with LRU; suggestion results cached per query/user context for TTL.
- Personalization uses recent high-rated selections; negative feedback reduces rank.
- Business rules: featured, plan level (premium/gold/platinum), priority score, recency via fields you supply.
- Geo: supports user coordinates and member coordinates; radius filter and distance-based boosts.

## Security
- API key required for all endpoints (except health).
- Simple per-key rate limiting (minute window).
- Parameterized SQL everywhere.

## Production Tips
- Use Gunicorn/uWSGI for serving in production:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
- Put the app behind a reverse proxy with TLS and WAF.
- Monitor latency and error rates; adjust rate limits and cache TTL.
- Back up SQLite or migrate to a managed DB for scale.