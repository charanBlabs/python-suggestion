#!/usr/bin/env python3
"""
Simple concurrent load test for the AI Search Suggestions API.
Simulates multiple users sending /suggest requests and records latency and errors.

Usage:
  python load_test.py --concurrency 20 --requests 200 --base-url http://127.0.0.1:5000 --api-key demo-key
"""

import argparse
import concurrent.futures
import random
import string
import time
from statistics import mean, median
import requests


def random_user_id(prefix: str = "user") -> str:
    return f"{prefix}_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


def make_request(base_url: str, api_key: str, idx: int) -> dict:
    user_id = random_user_id("u")
    # Alternate queries to exercise synonyms, intents, and geo
    queries = [
        "plumber near me",
        "book dentist in New York",
        "compare injury lawyer miami",
        "best daycare around",
        "emergency electrician nearby",
    ]
    query = queries[idx % len(queries)]
    payload = {
        "current_query": query,
        "user_id": user_id,
        "user_search_history": ["plumber", "dentist"],
        "user_location": "New York, NY",
        "user_latitude": 40.7128,
        "user_longitude": -74.0060,
        "debug": False,
        "site_data": {
            "settings": {"radius_km": 50},
            "members": [
                {"id": 1, "name": "Mike's Plumbing", "tags": "plumber, drain cleaning", "location": "New York, NY", "rating": 4.7, "latitude": 40.713, "longitude": -74.005, "profile_url": "https://example.com/m/1"},
                {"id": 2, "name": "Downtown Dental", "tags": "dentist, family", "location": "New York, NY", "rating": 4.9, "latitude": 40.714, "longitude": -74.002, "profile_url": "https://example.com/m/2"}
            ]
        }
    }

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    start = time.perf_counter()
    try:
        r = requests.post(f"{base_url.rstrip('/')}/suggest", json=payload, headers=headers, timeout=15)
        elapsed = (time.perf_counter() - start) * 1000.0
        return {
            "status": r.status_code,
            "ok": r.ok,
            "ms": elapsed,
            "error": None if r.ok else r.text[:200]
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000.0
        return {"status": 0, "ok": False, "ms": elapsed, "error": str(e)[:200]}


def run_load_test(base_url: str, api_key: str, total_requests: int, concurrency: int):
    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, base_url, api_key, i) for i in range(total_requests)]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())
    t1 = time.time()

    latencies = [r["ms"] for r in results]
    oks = [r for r in results if r["ok"]]
    errs = [r for r in results if not r["ok"]]

    throughput = total_requests / (t1 - t0) if (t1 - t0) > 0 else float('inf')
    print("=== Load Test Results ===")
    print(f"Requests: {total_requests}  Concurrency: {concurrency}")
    print(f"Duration: {t1 - t0:.2f}s  Throughput: {throughput:.2f} req/s")
    if latencies:
        print(f"Latency (ms): mean={mean(latencies):.1f}  p50={median(latencies):.1f}  min={min(latencies):.1f}  max={max(latencies):.1f}")
    print(f"Success: {len(oks)}  Errors: {len(errs)}")

    # Basic error breakdown
    from collections import Counter
    status_counts = Counter([r["status"] for r in errs])
    if status_counts:
        print("Error status codes:", dict(status_counts))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--api-key", default="demo-key")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    run_load_test(args.base_url, args.api_key, args.requests, args.concurrency)


if __name__ == "__main__":
    main()


