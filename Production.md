# Production and Free Hosting Guide

This guide shows two paths:
- Free/low-cost hosting options to get the API online quickly
- A production-grade deployment with security, scaling, and reliability

## Prerequisites
- Python 3.9+
- Git
- Your API key(s) set in environment: `API_KEYS=demo-key`
- Downloaded spaCy model: `python -m spacy download en_core_web_sm`

## Option A: Free Hosting (quickest)

Note: Free tiers change often. Below are commonly available options with zero or near-zero cost suitable for demos and light traffic. Expect cold starts and sleep timeouts.

### A1) Railway (Starter free credits)
1. Create a Railway account.
2. New Project → Deploy from GitHub (push this repo to GitHub first).
3. Add Service → Select your repo.
4. Set Environment Variables:
   - `API_KEYS=demo-key`
   - `DB_PATH=/data/ai_suggestions.db` (Railway provides persistent storage add-on or use default if not available)
   - `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`
   - `SUGGESTION_CACHE_TTL_SECONDS=300`
5. Start Command:
   - `python -m spacy download en_core_web_sm && python app.py`
6. Expose Port 5000 (Railway auto-detects). Copy the public URL and test `GET /`.

Tips
- If you hit memory/time limits loading SentenceTransformer, try a smaller model or upgrade plan.

### A2) Render (Free Web Service)
1. Create a Render account.
2. New + → Web Service → Connect repo.
3. Build Command:
   - `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
4. Start Command:
   - `python app.py`
5. Environment Variables:
   - `API_KEYS=demo-key`
   - `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`
   - `RATE_LIMIT_PER_MINUTE=120`
6. Select Free instance type. Deploy and test the public URL.

Notes
- Free instances may sleep; first request after idle will be slower.

### A3) Deta Space (Always-free micro)
1. Install `pip install deta` and create a Deta account.
2. Create a simple `main.py` wrapper with `FastAPI` or `flask` supported template if needed. Deta favors `FastAPI`; for Flask, use `wsgi` mode.
3. Initialize project: `deta new` and follow prompts.
4. Add `requirements.txt`, `app.py`, and set entrypoint.
5. Deploy: `deta deploy`.
6. Set `API_KEYS` and other env vars in the Deta Space dashboard.

Caveats
- File system is ephemeral; prefer Deta Base or an external DB instead of SQLite.

### A4) Hugging Face Spaces (Demo-only)
- Works best with Gradio/Streamlit UIs. For a plain Flask API, you’ll need a `spaces`-compatible wrapper and allow public HTTP. Use only for demos.

## Option B: Production-Grade Deployment

### B1) Containerize
Create `Dockerfile`:
```Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && python -m spacy download en_core_web_sm
COPY . .
ENV PORT=5000
CMD ["gunicorn", "-w", "4", "-k", "gthread", "--threads", "8", "-b", "0.0.0.0:5000", "app:app"]
```

Build and run:
```bash
docker build -t bd-suggest:latest .
docker run -p 5000:5000 \
  -e API_KEYS="prod-key-1,prod-key-2" \
  -e DB_PATH="/data/ai_suggestions.db" \
  -e RATE_LIMIT_PER_MINUTE=600 \
  -v $(pwd)/data:/data \
  bd-suggest:latest
```

### B2) Reverse Proxy + TLS (Nginx + Certbot)
1. Provision a VM (e.g., Ubuntu 22.04) on a cloud provider.
2. Point your domain DNS (A/AAAA) to the VM.
3. Install Docker and Docker Compose.
4. Run the app container (as above) on internal port 5000.
5. Nginx config (proxy to `http://localhost:5000`):
```nginx
server {
    listen 80;
    server_name api.example.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
6. Install Certbot and get certificates:
```bash
sudo apt-get update && sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com --redirect
```

### B3) Database & Storage
- SQLite is fine for small/solo deployments. For scale:
  - Use Postgres/MySQL managed service; migrate the `search_history`, `manual_data`, `events` tables
  - Use a proper ORM and migrations
  - Externalize file/data storage (don’t rely on container FS)

### B4) Performance & Scaling
- Gunicorn workers: start with `workers = CPU cores x 2`, `threads = 4-8`
- Enable instance autoscaling at the orchestrator level (Kubernetes/Render/Cloud Run)
- Cache: keep `SUGGESTION_CACHE_TTL_SECONDS` reasonable; consider Redis for shared cache
- Model warmup: hit `/suggest` on startup with a dummy request

### B5) Security & Reliability
- Require `X-API-Key` (already implemented)
- Enforce IP rate limiting at proxy (e.g., Nginx `limit_req`)
- Rotate API keys; store secrets in a vault
- Enable HTTPS (TLS) and HSTS
- Add health checks: `GET /` for liveness; optionally a deeper readiness check
- Logging: ship logs to a central system (e.g., CloudWatch, ELK)
- Monitoring: track p50/p95 latency, 4xx/5xx rates, CPU/RAM
- Backups: schedule DB backups; test restore

### B6) Configuration Matrix
Environment variables to set per environment:
- `PORT` (default: 5000)
- `DB_PATH` or DSN for external DB
- `API_KEYS` (comma-separated)
- `RATE_LIMIT_PER_MINUTE` (raise for paid plans)
- `EMBEDDING_MODEL` (ensure availability)
- `SUGGESTION_CACHE_TTL_SECONDS`

### B7) Postman and CI
- Keep `AI_Search_Suggestions_API.postman_collection.json` in source control
- Run basic smoke tests in CI (Newman) on deploy

## Troubleshooting
- Model download timeouts → build model into the image or pre-download in the build step
- 429 Too Many Requests → increase `RATE_LIMIT_PER_MINUTE` or use multiple keys
- High latency on cold start → use a warmup job; avoid free dyno sleep for production
- SQLite locked errors → switch to Postgres for concurrent writes

## Checklist (Production)
- [ ] Containerized with Gunicorn
- [ ] Reverse proxy with TLS
- [ ] External DB + backups
- [ ] Secrets and API keys managed securely
- [ ] Monitoring and alerts in place
- [ ] Rate limiting and WAF at the edge
- [ ] Load test executed and limits documented
