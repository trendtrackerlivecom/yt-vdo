# WebSearch — one page, every source

A small Flask app that collects live search results from several sources and
shows them together on one clean page.

## Sources
- **Bing** — HTML results page
- **DuckDuckGo** — HTML results page
- **Brave Search** — HTML results page
- **Mojeek** — HTML results page
- **Wikipedia** — official API (quick-fact card + articles)

All sources are queried in parallel; whichever answer are merged,
de-duplicated and shown with a per-source count. Some engines block
datacenter IPs, so the counts on the page show exactly which sources
responded from the host.

Google cannot be scraped reliably from a server (CAPTCHA wall for
datacenter IPs), so the page offers an "Open this search in Google"
button instead. A Google Programmable Search API key can be plugged
into `app.py` later if wanted.

## Render Docker deployment
1. Push all project files to the GitHub repository root.
2. Web Service → Docker environment.
3. Deploy with **Clear build cache & deploy**.
4. Open `/health` — should return `{"status":"ok", ...}`.

## Note
The previous YT-VDO downloader version lives in this repo's Git history
(and in a local backup) and can be restored at any time.
