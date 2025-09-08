# Brilliant Directories Integration Guide (Step-by-Step)

This guide shows how to plug the AI Search Suggestions API into a live Brilliant Directories (BD) site, end-to-end.

Prerequisites
- Running API (see README and Production.md). Note your `BASE_URL` and `X-API-Key`.
- Access to BD Admin → Content → Web Page Builder and Design Settings.
- Ability to upload small PHP helper files to your server (optional, for proxying).

Overview
- Option 1 (Direct): BD frontend calls the API directly from the browser using JS (requires CORS enabled on API; already enabled in app.py via CORS(app)).
- Option 2 (Proxy via PHP): Frontend calls your server PHP (e.g., `frontend_suggest.php`) which forwards to the API (no CORS issues, recommended).

1) Configure API Key on your server
- Place the three helper PHP files from this repo on your BD hosting (recommended in a custom folder):
  - `frontend_suggest.php`
  - `frontend_add_data.php`
  - `frontend_get_data.php`
- Set environment variables (in `.htaccess` or vhost config) or hardcode in the PHP files:
  - `API_BASE_URL` → your API base, e.g., `https://api.example.com`
  - `API_KEY` → your API key

2) Add the Suggestion UI to the Search Bar
- In BD Admin → Content → Web Page Builder → Find the page with your search bar (often Header or Home).
- Add this HTML where your search input lives (example):
```html
<input id="ai-search" type="text" class="form-control" placeholder="Search services..." autocomplete="off">
<div id="ai-suggest-box" class="dropdown-menu" style="display:none; max-height:280px; overflow:auto;"></div>
```
- Add CSS (Design Settings → Advanced Settings → Custom CSS):
```css
#ai-suggest-box { position:absolute; z-index:9999; width:100%; }
#ai-suggest-box .suggest-item { padding:8px 12px; cursor:pointer; }
#ai-suggest-box .suggest-item:hover { background:#f5f5f5; }
#ai-suggest-box .card { display:flex; align-items:center; gap:8px; }
#ai-suggest-box img { width:28px; height:28px; border-radius:3px; object-fit:cover; }
```
- Add JS (Design Settings → Advanced Settings → Footer Scripts) to call your PHP proxy:
```html
<script>
(function(){
  const input = document.getElementById('ai-search');
  const box = document.getElementById('ai-suggest-box');
  const endpoint = '/frontend_suggest.php'; // adjust path
  let timer = null;

  function hide(){ box.style.display = 'none'; box.innerHTML=''; }
  function show(){ box.style.display = 'block'; }
  function render(list, cards){
    const items = [];
    (list||[]).forEach(s => items.push(`<div class="suggest-item" data-text="${s.replace(/"/g,'&quot;')}">${s}</div>`));
    (cards||[]).forEach(c => items.push(`
      <div class="suggest-item">
        <div class="card">
          ${c.thumbnail_url ? `<img src="${c.thumbnail_url}" alt="">` : ''}
          <div>
            <div><strong>${c.title||''}</strong> ${c.rating?`<span>⭐ ${c.rating}</span>`:''}</div>
            ${c.location?`<div>${c.location}</div>`:''}
          </div>
        </div>
      </div>`));
    box.innerHTML = items.join('');
    if(items.length) show(); else hide();
  }

  input.addEventListener('input', function(){
    const q = input.value.trim();
    if (timer) clearTimeout(timer);
    if (!q){ hide(); return; }
    timer = setTimeout(async ()=>{
      try{
        const params = new URLSearchParams({ q, uid: 'bd_user', loc: '', lat: '', lon: '' });
        const res = await fetch(`${endpoint}?${params.toString()}`, { credentials:'same-origin' });
        const json = await res.json();
        render(json.suggestions, json.cards);
      }catch(e){ hide(); }
    }, 200);
  });

  document.addEventListener('click', function(ev){
    if (ev.target.classList.contains('suggest-item')){
      const text = ev.target.getAttribute('data-text');
      if (text){ input.value = text; hide(); }
      // optionally redirect to a search results page
      // window.location.href = `/search?keywords=${encodeURIComponent(text)}`;
    } else if(!box.contains(ev.target) && ev.target !== input){ hide(); }
  });
})();
</script>
```

3) Capture Feedback (optional but recommended)
- When a user clicks a suggestion, call `/feedback` via your PHP proxy to improve learning.
- Example (Footer Scripts):
```html
<script>
function sendAISuggestionFeedback(opts){
  fetch('/frontend_add_feedback.php', {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify(opts)
  });
}
</script>
```
- Implement `frontend_add_feedback.php` (clone of `frontend_add_data.php` style) to POST to `/feedback`.

4) Add Data into the Engine
- For small manual adds: use `frontend_add_data.php` from the server or Postman to `/data`.
- For daily BD export (recommended): map your BD member/category exports to the API schema and call `/batch_import` nightly (use cron on your server).
- Minimal member fields that help ranking:
  - `id`, `name`, `tags` (comma string), `location`, `rating`, optional `latitude`, `longitude`, `profile_url`, `thumbnail_url`, `featured`, `plan_level`, `priority_score`.

5) Fetch Stored Data (for admin UI)
- Use `frontend_get_data.php?type=member` to list what’s currently loaded in the engine.
- Build a simple BD Admin Page (Web Page Builder) that calls this endpoint and renders a table.

6) Geo & Settings
- If you want a global radius (instead of per-request `site_data.settings.radius_km`), keep it simple:
  - Hardcode a default in `app.py` (site_data fallback) or
  - Add a `settings` record via `/data` (type: `whitelist`/`synonym` doesn’t hold it yet). If you want, we can add a persistent `settings` type; otherwise use env var.

7) Event Tracking (CTR/conversions)
- On click-through to a member profile or contact button, call `/event` via a PHP endpoint:
```php
// example minimal payload
// POST /event { user_id, event_type:"member_click", payload:{ member_id, profile_url } }
```
- These events appear in `GET /analytics` as counts by type.

8) Rate Limiting & Keys
- API requires `X-API-Key`. Set one key for production and one for staging.
- If users share one key from the browser, keep RATE_LIMIT_PER_MINUTE high enough, or proxy all calls via your server and implement per-IP throttling.

9) Testing
- Use the bundled Postman collection. Set `X-API-Key` variable and your `base_url`.
- Verify `/suggest` returns both `suggestions` and `cards`.
- Run `python load_test.py` locally to estimate throughput.

FAQ
- Do I need to send `site_data` on every request? No. Load your data daily via `/batch_import` or ad-hoc via `/data`. Then call `/suggest` with only the query/user info.
- Can I customize suggestion templates? Yes—adjust templates in `app.py` or create custom ones per intent.
- How do I show only members? Use the `cards` array and render it as a list/grid under the search.

Support
- If you need a dedicated BD-specific settings type, ping me—I can add `type: "settings"` persistence and wire global options like `radius_km` and default intents.
