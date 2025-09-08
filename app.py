#!/usr/bin/env python3
# app.py (BD Extended Version)
# Intelligent Search Suggestion Microservice for Brilliant Directories
# Features:
# - Supports Top, Sub, Sub-Sub categories
# - Member metadata: tags, location, reviews, rating
# - Hybrid Ranking: semantic + BM25 + personalization
# - Suggestion rewrites

import os
import re
import json
import sqlite3
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from functools import lru_cache
from datetime import datetime, timedelta
import pickle

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pyngrok import ngrok

import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import spacy
import nltk
from nltk.corpus import wordnet as wn

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ---------------------------
# App & Globals
# ---------------------------
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

app = Flask(__name__)
CORS(app)

_model: Optional[SentenceTransformer] = None
nlp = spacy.load("en_core_web_sm")

# Database setup
DB_PATH = os.environ.get("DB_PATH", "ai_suggestions.db")
API_KEYS = set([k.strip() for k in os.environ.get("API_KEYS", "demo-key").split(",") if k.strip()])

# Simple in-memory rate limiter: {key: {window_start, count}}
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))
_rate_limit_state: Dict[str, Dict[str, float]] = defaultdict(dict)

def require_api_key():
    key = request.headers.get("X-API-Key")
    if not key or key not in API_KEYS:
        return False
    # rate limiting per API key
    now = datetime.utcnow()
    window = now.replace(second=0, microsecond=0)
    state = _rate_limit_state.get(key)
    if not state or state.get("window") != window:
        _rate_limit_state[key] = {"window": window, "count": 1}
    else:
        _rate_limit_state[key]["count"] += 1
    if _rate_limit_state[key]["count"] > RATE_LIMIT_PER_MINUTE:
        return "rate_limited"
    return True

# Session cache for personalization
USER_HISTORY_CACHE = defaultdict(list)
# Cache for popular queries
SUGGESTION_CACHE: Dict[str, Dict] = {}
SUGGESTION_CACHE_TTL_SECONDS = int(os.environ.get("SUGGESTION_CACHE_TTL_SECONDS", "300"))
POPULAR_QUERIES: defaultdict = defaultdict(int)

# Learning data storage
LEARNING_DATA = {
    "query_patterns": defaultdict(int),
    "successful_suggestions": defaultdict(int),
    "user_preferences": defaultdict(dict),
    "location_patterns": defaultdict(int)
}

# Weights (can be adjusted based on learning)
WEIGHT_SEMANTIC = 0.7
WEIGHT_BM25 = 0.3
BOOST_HISTORY = 0.1
BOOST_HIGH_RATING = 0.1
BOOST_LOCATION_MATCH = 0.1
BOOST_LEARNED_PATTERN = 0.15

_word_re = re.compile(r"[a-zA-Z][a-zA-Z-']+")

# ---------------------------
# Database & Learning Utils
# ---------------------------
def init_database():
    """Initialize SQLite database for persistent storage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Search history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            query TEXT,
            suggestions TEXT,
            selected_suggestion TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            location TEXT,
            success_rating INTEGER DEFAULT 0,
            ab_variant TEXT
        )
    ''')
    
    # Manual data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manual_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT, -- 'category', 'member', 'location', 'profession'
            data_content TEXT, -- JSON content
            added_by TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Learning patterns table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT, -- 'query', 'suggestion', 'location'
            pattern_key TEXT,
            pattern_value TEXT,
            frequency INTEGER DEFAULT 1,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Events table for conversions/clicks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event_type TEXT,
            payload TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Attempt to add missing columns for migrations
    try:
        cursor.execute("ALTER TABLE search_history ADD COLUMN ab_variant TEXT")
    except Exception:
        pass
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully")

def save_search_interaction(user_id: str, query: str, suggestions: List[str], 
                          selected: Optional[str] = None, location: Optional[str] = None,
                          success_rating: int = 0):
    """Save search interaction for learning"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO search_history 
        (user_id, query, suggestions, selected_suggestion, location, success_rating)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, query, json.dumps(suggestions), selected, location, success_rating))
    
    conn.commit()
    conn.close()
    
    # Update learning patterns
    LEARNING_DATA["query_patterns"][query.lower()] += 1
    if selected:
        LEARNING_DATA["successful_suggestions"][selected.lower()] += 1
    if location:
        LEARNING_DATA["location_patterns"][location.lower()] += 1

def get_user_preferences(user_id: str) -> Dict:
    """Get learned user preferences"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT query, selected_suggestion, success_rating
        FROM search_history 
        WHERE user_id = ? AND success_rating > 3
        ORDER BY timestamp DESC LIMIT 50
    ''', (user_id,))
    
    preferences = defaultdict(int)
    for row in cursor.fetchall():
        query, selected, rating = row
        if selected:
            preferences[selected.lower()] += rating
    
    conn.close()
    return dict(preferences)

def get_user_negative_preferences(user_id: str) -> Dict:
    """Collect negatively rated suggestions to suppress"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT selected_suggestion, success_rating FROM search_history
        WHERE user_id = ? AND selected_suggestion IS NOT NULL AND success_rating <= 2
        ORDER BY timestamp DESC LIMIT 100
    ''', (user_id,))
    negatives = defaultdict(int)
    for row in cursor.fetchall():
        selected, rating = row
        negatives[(selected or '').lower()] += (3 - int(rating or 0))
    conn.close()
    return dict(negatives)

def add_manual_data(data_type: str, data_content: Dict, added_by: str = "admin"):
    """Add manual data to the system"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO manual_data (data_type, data_content, added_by)
        VALUES (?, ?, ?)
    ''', (data_type, json.dumps(data_content), added_by))
    
    conn.commit()
    conn.close()
    logging.info(f"Added manual {data_type} data: {data_content}")

def get_manual_data(data_type: Optional[str] = None) -> List[Dict]:
    """Retrieve manual data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if data_type:
        cursor.execute('''
            SELECT data_content FROM manual_data 
            WHERE data_type = ? AND is_active = 1
        ''', (data_type,))
    else:
        cursor.execute('''
            SELECT data_type, data_content FROM manual_data 
            WHERE is_active = 1
        ''')
    
    results = []
    for row in cursor.fetchall():
        if data_type:
            results.append(json.loads(row[0]))
        else:
            results.append({"type": row[0], "content": json.loads(row[1])})
    
    conn.close()
    return results

# ---------------------------
# Quality Controls & Ontology
# ---------------------------
def get_synonyms_map() -> Dict[str, List[str]]:
    maps = {}
    for item in get_manual_data("synonym"):
        base = (item.get("base") or "").lower()
        terms = [t.lower() for t in item.get("terms", [])]
        if base:
            maps[base] = terms
    return maps

def get_blacklist() -> List[str]:
    return [(item.get("term") or "").lower() for item in get_manual_data("blacklist") if item.get("term")]

def get_whitelist() -> List[str]:
    return [(item.get("term") or "").lower() for item in get_manual_data("whitelist") if item.get("term")]

# ---------------------------
# Utils
# ---------------------------
def tokenize(text: str) -> List[str]:
    return [w.lower() for w in _word_re.findall(text or "")]

@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logging.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return normalize(a) @ normalize(b).T

def expand_synonyms(word: str) -> List[str]:
    synonyms = set()
    for syn in wn.synsets(word):
        for lemma in syn.lemmas():
            synonyms.add(lemma.name().replace("_", " "))
    return list(synonyms)

def detect_locations(text: str) -> List[str]:
    doc = nlp(text)
    return [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers"""
    from math import radians, cos, sin, asin, sqrt
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def get_location_boost(user_lat: Optional[float], user_lon: Optional[float], 
                      candidate_location: Optional[str]) -> float:
    """Calculate location-based boost for candidates"""
    if not user_lat or not user_lon or not candidate_location:
        return 0.0
    
    # This is a simplified version - in production you'd use a geocoding service
    # to convert location strings to coordinates
    boost = 0.0
    
    # Simple text-based location matching
    location_keywords = ["near", "nearby", "close", "local", "around"]
    for keyword in location_keywords:
        if keyword in candidate_location.lower():
            boost += 0.05
    
    return min(boost, 0.2)  # Cap the boost

# ---------------------------
# Candidate building
# ---------------------------
def build_candidates(site_data: Dict) -> List[Dict]:
    """
    Build candidates from categories, member metadata, and manual data.
    Each candidate is {text, type, extra}
    """
    candidates = []

    # Categories (Top → Sub → Subsub)
    for cat in site_data.get("categories", []):
        top = cat.get("top_category", "").strip()
        sub = cat.get("sub_category", "").strip()
        subsub = cat.get("sub_sub_category", "").strip()

        if top:
            candidates.append({"text": top, "type": "category"})
        if top and sub:
            candidates.append({"text": f"{top} - {sub}", "type": "subcategory"})
        if top and sub and subsub:
            candidates.append({"text": f"{top} - {sub} - {subsub}", "type": "subsubcategory"})

    # Members
    for mem in site_data.get("members", []):
        name = mem.get("name", "").strip()
        tags = (mem.get("tags") or "").split(",")
        location = mem.get("location", "").strip()
        reviews = mem.get("reviews", "")
        rating = float(mem.get("rating", 0))
        profile_url = mem.get("profile_url")
        thumbnail_url = mem.get("thumbnail_url")
        member_id = mem.get("id")
        latitude = mem.get("latitude")
        longitude = mem.get("longitude")
        featured = bool(mem.get("featured", False))
        plan_level = mem.get("plan_level")
        priority_score = float(mem.get("priority_score", 0))
        last_updated = mem.get("last_updated")
        promo_badge = mem.get("promo_badge")
        hours = mem.get("hours")

        base_cand = {
            "text": name or "",
            "type": "member",
            "rating": rating,
            "location": location,
            "profile_url": profile_url,
            "thumbnail_url": thumbnail_url,
            "id": member_id,
            "latitude": latitude,
            "longitude": longitude,
            "featured": featured,
            "plan_level": plan_level,
            "priority_score": priority_score,
            "last_updated": last_updated,
            "promo_badge": promo_badge,
            "hours": hours,
        }
        if name:
            candidates.append(dict(base_cand))
        for t in [tt.strip() for tt in tags if tt.strip()]:
            tag_cand = dict(base_cand)
            tag_cand.update({"text": t, "type": "tag"})
            candidates.append(tag_cand)
        if reviews:
            rev_cand = dict(base_cand)
            rev_cand.update({"text": reviews, "type": "review"})
            candidates.append(rev_cand)

    # Add manual data
    manual_data = get_manual_data()
    for item in manual_data:
        data_type = item["type"]
        content = item["content"]
        
        if data_type == "category":
            candidates.append({"text": content.get("name", ""), "type": "manual_category"})
        elif data_type == "member":
            name = content.get("name", "")
            location = content.get("location", "")
            rating = content.get("rating", 0)
            if name:
                candidates.append({"text": name, "type": "manual_member", "rating": rating, "location": location})
        elif data_type == "profession":
            candidates.append({"text": content.get("name", ""), "type": "manual_profession"})
        elif data_type == "location":
            candidates.append({"text": content.get("name", ""), "type": "manual_location"})

    # Dedup
    seen, uniq = set(), []
    for c in candidates:
        if c["text"].lower() not in seen:
            uniq.append(c)
            seen.add(c["text"].lower())
    return uniq

# ---------------------------
# Hybrid Ranking
# ---------------------------
def hybrid_rank(query: str, candidates: List[Dict]) -> List[Tuple[Dict, float]]:
    model = get_model()
    # Expand query with manual synonyms
    synonyms_map = get_synonyms_map()
    expanded_query_parts = [query]
    for base, terms in synonyms_map.items():
        if base in query.lower():
            expanded_query_parts.extend(terms)
    expanded_query = " ".join(expanded_query_parts)

    texts = [c["text"] for c in candidates]
    embeddings = model.encode([expanded_query] + texts, convert_to_numpy=True)
    q_vec, c_vecs = embeddings[0:1], embeddings[1:]
    semantic_scores = cosine_similarity(q_vec, c_vecs).ravel()

    tokenized_cands = [tokenize(c["text"]) for c in candidates]
    bm25 = BM25Okapi(tokenized_cands)
    bm25_scores = bm25.get_scores(tokenize(expanded_query))

    combined = WEIGHT_SEMANTIC * semantic_scores + WEIGHT_BM25 * bm25_scores
    return list(zip(candidates, combined))

# ---------------------------
# Suggestion Rewriting
# ---------------------------
TEMPLATES = [
    "Top-rated {base} near you",
    "Affordable {base} in {city}",
    "Trusted {base} nearby",
    "Best {base} in {city}",
    "Experienced {base} near me"
]

def rewrite_suggestion(base: str, city: Optional[str]) -> List[str]:
    return [tpl.format(base=base, city=city or "[City]") for tpl in TEMPLATES]

def detect_intent(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["book", "schedule", "reserve"]):
        return "book"
    if any(w in q for w in ["hire", "find", "near me", "nearby"]):
        return "hire"
    if any(w in q for w in ["review", "reviews", "rating"]):
        return "review"
    if any(w in q for w in ["compare", "vs", "best"]):
        return "compare"
    return "generic"

INTENT_TEMPLATES = {
    "book": [
        "Book {base} in {city}",
        "Schedule with {base} near you",
        "Reserve {base} today"
    ],
    "hire": [
        "Top-rated {base} near you",
        "Best {base} in {city}",
        "Trusted {base} nearby"
    ],
    "review": [
        "Highest-rated {base} in {city}",
        "{base} with great reviews",
        "Most trusted {base} near you"
    ],
    "compare": [
        "Compare {base} in {city}",
        "Top {base} options near you",
        "Best {base} nearby"
    ],
    "generic": TEMPLATES,
}

def rewrite_with_intent(base: str, city: Optional[str], intent: str) -> List[str]:
    templates = INTENT_TEMPLATES.get(intent, TEMPLATES)
    return [tpl.format(base=base, city=city or "[City]") for tpl in templates]

# ---------------------------
# Main Ranking Pipeline
# ---------------------------
def _is_open_now(hours: Optional[Dict]) -> bool:
    if not hours or not isinstance(hours, dict):
        return False
    # Expect format: {"mon": [["09:00","17:00"]], ...}
    now = datetime.now()
    weekday = ["mon","tue","wed","thu","fri","sat","sun"][now.weekday()]
    intervals = hours.get(weekday, [])
    current = now.strftime("%H:%M")
    for start, end in intervals:
        if start <= current <= end:
            return True
    return False

def rank_candidates(query: str, site_data: Dict, user_id: str, history: List[str], 
                   user_lat: Optional[float] = None, user_lon: Optional[float] = None,
                   debug: bool = False, ab_variant: Optional[str] = None) -> Tuple[List[str], List[Dict], Optional[Dict]]:
    # Cache key: query + basic site_data fingerprint
    cache_key = json.dumps({
        "q": query,
        "uid": user_id,
        "lat": user_lat,
        "lon": user_lon,
        "intent": detect_intent(query),
        "radius": site_data.get("settings", {}).get("radius_km")
    }, sort_keys=True)
    now_ts = datetime.utcnow().timestamp()
    cached = SUGGESTION_CACHE.get(cache_key)
    if cached and (now_ts - cached.get("ts", 0) <= SUGGESTION_CACHE_TTL_SECONDS):
        return cached["suggestions"], cached["cards"], cached.get("debug") if debug else (cached["suggestions"], cached["cards"], None)

    candidates = build_candidates(site_data)
    if not candidates:
        # Cold-start: return top manual categories/professions
        cold = []
        for item in get_manual_data("category") + get_manual_data("profession"):
            name = item.get("name")
            if name:
                cold.append(name)
        cold = cold[:5] or ["Popular services near you"]
        return cold, [], {"reason": "cold_start"} if debug else (cold, [], None)

    ranked = hybrid_rank(query, candidates)
    locs = detect_locations(query)
    city = locs[0] if locs else None

    # Get user preferences for learning-based boosting
    user_prefs = get_user_preferences(user_id)
    user_negs = get_user_negative_preferences(user_id)

    # Apply boosts
    scores = []
    radius_km = None
    try:
        radius_km = float(site_data.get("settings", {}).get("radius_km"))
    except Exception:
        radius_km = None
    blacklist = set(get_blacklist())
    whitelist = set(get_whitelist())
    intent = detect_intent(query)
    for cand, sc in ranked:
        boost = 0.0
        text = cand["text"]

        # Quality controls
        if blacklist and any(b in text.lower() for b in blacklist):
            continue
        if whitelist and not any(w in text.lower() for w in whitelist):
            pass  # optional light boost if needed

        # History boost
        for h in history + USER_HISTORY_CACHE[user_id]:
            if h.lower() in text.lower():
                boost += BOOST_HISTORY

        # Rating boost
        if cand.get("rating", 0) >= 4.5:
            boost += BOOST_HIGH_RATING

        # Location boost
        if city and cand.get("location") and city.lower() in cand["location"].lower():
            boost += BOOST_LOCATION_MATCH
        
        # Enhanced location boost with coordinates
        distance_km = None
        if user_lat and user_lon and (cand.get("latitude") is not None) and (cand.get("longitude") is not None):
            try:
                distance_km = calculate_distance(float(user_lat), float(user_lon), float(cand["latitude"]), float(cand["longitude"]))
                # distance decay: within 5km strong, 5-20 moderate
                if distance_km <= 5:
                    boost += 0.15
                elif distance_km <= 20:
                    boost += 0.08
                else:
                    boost += 0.0
                # radius filter
                if radius_km is not None and distance_km > radius_km:
                    continue
            except Exception:
                pass
        elif user_lat and user_lon and cand.get("location"):
            boost += get_location_boost(user_lat, user_lon, cand["location"])

        # Learning-based boost
        if text.lower() in user_prefs:
            boost += BOOST_LEARNED_PATTERN * (user_prefs[text.lower()] / 10.0)
        if text.lower() in user_negs:
            boost -= BOOST_LEARNED_PATTERN * (user_negs[text.lower()] / 5.0)

        # Pattern-based boost from learning data
        if text.lower() in LEARNING_DATA["successful_suggestions"]:
            boost += BOOST_LEARNED_PATTERN * 0.5

        # Business rules
        if cand.get("featured"):
            boost += 0.1
        if cand.get("plan_level") in ("premium", "gold", "platinum"):
            boost += 0.08
        boost += float(cand.get("priority_score", 0)) * 0.05

        # Availability/promotions
        if _is_open_now(cand.get("hours")):
            boost += 0.05
        if cand.get("promo_badge"):
            boost += 0.03

        scores.append((cand, sc + boost, distance_km))

    scores.sort(key=lambda x: -x[1])

    # Rewrite top candidates into user-friendly suggestions
    suggestions = []
    cards = []
    for cand, _, dist in scores[:5]:
        # Suggestion text with intent
        suggestions.extend(rewrite_with_intent(cand["text"], city, intent))
        # Member card (only for member/tag-derived with profile_url or id)
        if cand.get("type") in ("member", "tag", "review") and (cand.get("profile_url") or cand.get("id")):
            cards.append({
                "title": cand["text"],
                "member_id": cand.get("id"),
                "profile_url": cand.get("profile_url"),
                "thumbnail_url": cand.get("thumbnail_url"),
                "rating": cand.get("rating"),
                "location": cand.get("location"),
                "distance_km": round(dist, 2) if dist is not None else None,
                "promo_badge": cand.get("promo_badge"),
                "featured": cand.get("featured", False),
            })

    # Dedup & limit to 5
    seen, final = set(), []
    for s in suggestions:
        if s.lower() not in seen:
            final.append(s)
            seen.add(s.lower())
        if len(final) >= 5:
            break

    # Cache query into user history
    if query not in USER_HISTORY_CACHE[user_id]:
        USER_HISTORY_CACHE[user_id].append(query)

    debug_info = None
    if debug:
        debug_info = {
            "intent": intent,
            "city": city,
            "top_candidates": [
                {
                    "text": c[0]["text"],
                    "type": c[0].get("type"),
                    "score": round(c[1], 4),
                    "distance_km": c[2]
                } for c in scores[:10]
            ]
        }

    # Update popular queries and set cache
    POPULAR_QUERIES[query.lower()] += 1
    SUGGESTION_CACHE[cache_key] = {"ts": now_ts, "suggestions": final, "cards": cards, "debug": debug_info}

    return final, cards, debug_info

# ---------------------------
# API Endpoint
# ---------------------------
@app.route("/suggest", methods=["POST"])
def suggest():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    data = request.get_json(force=True)
    query = data.get("current_query", "").strip()
    user_id = data.get("user_id", "anon")
    history = data.get("user_search_history", [])
    site_data = data.get("site_data", {})
    location = data.get("user_location", "")
    user_lat = data.get("user_latitude")
    user_lon = data.get("user_longitude")
    debug_flag = bool(data.get("debug", False))
    ab_variant = request.headers.get("X-AB-Variant") or data.get("ab_variant")

    if not query:
        return jsonify({"error": "current_query is required"}), 400

    try:
        suggestions, cards, debug_info = rank_candidates(query, site_data, user_id, history, user_lat, user_lon, debug_flag, ab_variant)
        
        # Save the search interaction for learning
        save_search_interaction(user_id, query, suggestions, location=location)
        # Record A/B variant in latest search_history row
        try:
            if ab_variant:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE search_history
                    SET ab_variant = ?
                    WHERE user_id = ? AND query = ? AND timestamp = (
                        SELECT MAX(timestamp) FROM search_history WHERE user_id = ? AND query = ?
                    )
                ''', (ab_variant, user_id, query, user_id, query))
                conn.commit()
                conn.close()
        except Exception:
            pass
        
        resp = {
            "original_query": query,
            "suggestions": suggestions,
            "cards": cards,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        if debug_flag and debug_info:
            resp["debug"] = debug_info
        return jsonify(resp)
    except Exception as e:
        logging.exception("Error generating suggestions")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return jsonify({"message": "AI Search Suggestions API is running!"})
@app.route("/feedback", methods=["POST"])

def feedback():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    """Endpoint to receive feedback on suggestions for learning"""
    data = request.get_json(force=True)
    user_id = data.get("user_id", "anon")
    query = data.get("query", "").strip()
    selected_suggestion = data.get("selected_suggestion", "").strip()
    success_rating = data.get("success_rating", 0)  # 1-5 scale
    location = data.get("location", "")

    if not query or not selected_suggestion:
        return jsonify({"error": "query and selected_suggestion are required"}), 400

    try:
        # Update the search history with feedback
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE search_history 
            SET selected_suggestion = ?, success_rating = ?
            WHERE user_id = ? AND query = ? AND timestamp > datetime('now', '-1 hour')
            ORDER BY timestamp DESC LIMIT 1
        ''', (selected_suggestion, success_rating, user_id, query))
        
        conn.commit()
        conn.close()
        
        # Update learning patterns
        LEARNING_DATA["successful_suggestions"][selected_suggestion.lower()] += success_rating
        
        return jsonify({"status": "feedback_received"})
    except Exception as e:
        logging.exception("Error processing feedback")
        return jsonify({"error": str(e)}), 500

@app.route("/data", methods=["POST"])
def add_data():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    """Endpoint to manually add data to the system"""
    data = request.get_json(force=True)
    data_type = data.get("type", "").strip()
    content = data.get("content", {})
    added_by = data.get("added_by", "admin")

    if not data_type or not content:
        return jsonify({"error": "type and content are required"}), 400

    valid_types = ["category", "member", "profession", "location", "synonym", "blacklist", "whitelist"]
    if data_type not in valid_types:
        return jsonify({"error": f"type must be one of: {valid_types}"}), 400

    try:
        add_manual_data(data_type, content, added_by)
        return jsonify({"status": "data_added", "type": data_type})
    except Exception as e:
        logging.exception("Error adding data")
        return jsonify({"error": str(e)}), 500

@app.route("/batch_import", methods=["POST"])
def batch_import():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    data = request.get_json(force=True)
    items = data.get("items", [])
    added_by = data.get("added_by", "batch")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items (array) is required"}), 400
    valid_types = {"category", "member", "profession", "location"}
    success, failed = 0, 0
    for it in items:
        try:
            t = (it.get("type") or "").strip()
            c = it.get("content", {})
            if t not in valid_types or not c:
                failed += 1
                continue
            add_manual_data(t, c, added_by)
            success += 1
        except Exception:
            failed += 1
    return jsonify({"status": "ok", "imported": success, "failed": failed})

@app.route("/data", methods=["GET"])
def get_data():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    """Endpoint to retrieve manual data"""
    data_type = request.args.get("type")
    
    try:
        data = get_manual_data(data_type)
        return jsonify({"data": data, "count": len(data)})
    except Exception as e:
        logging.exception("Error retrieving data")
        return jsonify({"error": str(e)}), 500

@app.route("/analytics", methods=["GET"])
def analytics():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    """Endpoint to get learning analytics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        start = request.args.get("start")
        end = request.args.get("end")
        out_format = request.args.get("format", "json")

        # Get search statistics
        if start and end:
            cursor.execute('''
                SELECT COUNT(*), COUNT(DISTINCT user_id), AVG(success_rating)
                FROM search_history
                WHERE timestamp BETWEEN ? AND ?
            ''', (start, end))
        else:
            cursor.execute('''
                SELECT COUNT(*), COUNT(DISTINCT user_id), AVG(success_rating)
                FROM search_history
            ''')
        stats = cursor.fetchone()
        
        # Get top queries
        if start and end:
            cursor.execute('''
                SELECT query, COUNT(*) as frequency
                FROM search_history
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY query
                ORDER BY frequency DESC
                LIMIT 10
            ''', (start, end))
        else:
            cursor.execute('''
                SELECT query, COUNT(*) as frequency
                FROM search_history
                GROUP BY query
                ORDER BY frequency DESC
                LIMIT 10
            ''')
        top_queries = cursor.fetchall()
        
        # Get top suggestions
        if start and end:
            cursor.execute('''
                SELECT selected_suggestion, COUNT(*) as frequency
                FROM search_history
                WHERE selected_suggestion IS NOT NULL AND timestamp BETWEEN ? AND ?
                GROUP BY selected_suggestion
                ORDER BY frequency DESC
                LIMIT 10
            ''', (start, end))
        else:
            cursor.execute('''
                SELECT selected_suggestion, COUNT(*) as frequency
                FROM search_history
                WHERE selected_suggestion IS NOT NULL
                GROUP BY selected_suggestion
                ORDER BY frequency DESC
                LIMIT 10
            ''')
        top_suggestions = cursor.fetchall()

        # Events count by type
        if start and end:
            cursor.execute('''
                SELECT event_type, COUNT(*) FROM events WHERE timestamp BETWEEN ? AND ? GROUP BY event_type
            ''', (start, end))
        else:
            cursor.execute('''
                SELECT event_type, COUNT(*) FROM events GROUP BY event_type
            ''')
        events_counts = cursor.fetchall()
        
        conn.close()
        
        payload = {
            "statistics": {
                "total_searches": stats[0],
                "unique_users": stats[1],
                "average_rating": round(stats[2] or 0, 2)
            },
            "top_queries": [{"query": q[0], "frequency": q[1]} for q in top_queries],
            "top_suggestions": [{"suggestion": s[0], "frequency": s[1]} for s in top_suggestions],
            "events": [{"event_type": e[0], "count": e[1]} for e in events_counts],
            "learning_patterns": dict(LEARNING_DATA["query_patterns"])
        }
        if out_format == "csv":
            # simple CSV export of top queries
            lines = ["query,frequency"] + [f"{q[0]},{q[1]}" for q in top_queries]
            return Response("\n".join(lines), mimetype='text/csv')
        return jsonify(payload)
    except Exception as e:
        logging.exception("Error getting analytics")
        return jsonify({"error": str(e)}), 500

@app.route("/event", methods=["POST"])
def track_event():
    auth = require_api_key()
    if auth is False:
        return jsonify({"error": "Unauthorized"}), 401
    if auth == "rate_limited":
        return jsonify({"error": "Too Many Requests"}), 429
    data = request.get_json(force=True)
    user_id = data.get("user_id", "anon")
    event_type = data.get("event_type")
    payload = data.get("payload", {})
    if not event_type:
        return jsonify({"error": "event_type is required"}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO events (user_id, event_type, payload) VALUES (?, ?, ?)
        ''', (user_id, event_type, json.dumps(payload)))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        logging.exception("Error tracking event")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "bd-suggest-extended", "model": MODEL_NAME})
    
public_url = ngrok.connect(5000)
print(" * ngrok tunnel \"{}\" -> \"http://127.0.0.1:5000\"".format(public_url))

if __name__ == "__main__":
    # Initialize database on startup
    init_database()
    
    # Download required NLTK data
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        nltk.download('wordnet')
    
    port = int(os.environ.get("PORT", 5000))
    #app.run(host="127.0.0.1", port=port, debug=False)
    app.run(port=5000)
