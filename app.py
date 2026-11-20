"""WebSearch — one search page that collects results from several sources.

Sources (server-side, no API keys needed):
  - Bing        (HTML results page)
  - DuckDuckGo  (HTML results page)
  - Wikipedia   (official API — quick-fact card + article link)

Google cannot be scraped reliably from a server (it answers datacenter IPs
with CAPTCHAs), so the page links out to Google for the same query instead.
If a Google Programmable Search API key is ever added, plug it into
google_api() below — the merge code already knows the result shape.
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 8
CACHE = {}
CACHE_TTL = 300  # seconds


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def norm_url(url):
    """Normalise a URL for de-duplication."""
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").rstrip("/")
        return host + path
    except Exception:
        return url


def unwrap_bing(href):
    """Bing wraps result links (bing.com/ck/a?...&u=a1<base64>) — decode them."""
    if "bing.com/ck/a" not in href:
        return href
    try:
        u = parse_qs(urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            import base64

            pad = "=" * (-len(u[2:]) % 4)
            return base64.urlsafe_b64decode(u[2:] + pad).decode("utf-8", "replace")
    except Exception:
        pass
    return href


def bing(query):
    url = f"https://www.bing.com/search?q={quote_plus(query)}&count=20"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for item in soup.select("li.b_algo"):
        a = item.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        snippet = item.select_one(".b_caption p")
        out.append(
            {
                "title": clean(a.get_text()),
                "url": unwrap_bing(a["href"]),
                "snippet": clean(snippet.get_text()) if snippet else "",
                "source": "Bing",
            }
        )
    return out


def brave(query):
    url = f"https://search.brave.com/search?q={quote_plus(query)}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for item in soup.select("div.snippet"):
        a = item.select_one("a[href^='http']")
        if not a:
            continue
        title_el = item.select_one(".title") or a
        snippet = item.select_one(".snippet-description")
        out.append(
            {
                "title": clean(title_el.get_text()),
                "url": a["href"],
                "snippet": clean(snippet.get_text()) if snippet else "",
                "source": "Brave",
            }
        )
    return out


def mojeek(query):
    url = f"https://www.mojeek.com/search?q={quote_plus(query)}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for item in soup.select("ul.results-standard li"):
        a = item.select_one("a.title")
        if not a or not a.get("href"):
            continue
        snippet = item.select_one("p.s")
        out.append(
            {
                "title": clean(a.get_text()),
                "url": a["href"],
                "snippet": clean(snippet.get_text()) if snippet else "",
                "source": "Mojeek",
            }
        )
    return out


def duckduckgo(query):
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for item in soup.select(".result"):
        a = item.select_one("a.result__a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        # DDG wraps result links: //duckduckgo.com/l/?uddg=<real url>
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            href = unquote(qs["uddg"][0])
        snippet = item.select_one(".result__snippet")
        out.append(
            {
                "title": clean(a.get_text()),
                "url": href,
                "snippet": clean(snippet.get_text()) if snippet else "",
                "source": "DuckDuckGo",
            }
        )
    return out


def wikipedia(query):
    """Return (fact_card_or_None, [article results])."""
    api = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=0&gsrlimit=3"
        "&prop=extracts|info&exintro&explaintext&inprop=url"
        f"&gsrsearch={quote_plus(query)}"
    )
    r = requests.get(api, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    pages = sorted(pages.values(), key=lambda p: p.get("index", 99))
    fact = None
    results = []
    for i, p in enumerate(pages):
        url = p.get("fullurl", "")
        extract = clean(p.get("extract", ""))
        if i == 0 and extract:
            fact = {
                "title": p.get("title", ""),
                "text": extract[:600],
                "url": url,
                "source": "Wikipedia",
            }
        results.append(
            {
                "title": p.get("title", ""),
                "url": url,
                "snippet": extract[:220],
                "source": "Wikipedia",
            }
        )
    return fact, results


def search_all(query):
    cached = CACHE.get(query.lower())
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    fetchers = (
        ("Bing", bing),
        ("DuckDuckGo", duckduckgo),
        ("Brave", brave),
        ("Mojeek", mojeek),
    )
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {name: ex.submit(fn, query) for name, fn in fetchers}
        f_wiki = ex.submit(wikipedia, query)

    sources = {}
    by_source = {}
    for name, fut in futures.items():
        try:
            by_source[name] = fut.result()
            sources[name] = len(by_source[name])
        except Exception:
            by_source[name] = []
            sources[name] = 0

    fact = None
    wiki_results = []
    try:
        fact, wiki_results = f_wiki.result()
        sources["Wikipedia"] = len(wiki_results)
    except Exception:
        sources["Wikipedia"] = 0

    # Interleave all web sources round-robin, de-duplicated by normalised URL.
    merged, seen = [], set()
    pools = [by_source[name] for name, _ in fetchers]
    for i in range(max((len(p) for p in pools), default=0)):
        for pool in pools:
            if i < len(pool):
                item = pool[i]
                key = norm_url(item["url"])
                if key not in seen:
                    seen.add(key)
                    merged.append(item)
    # Wikipedia articles not already present go right after the fact card.
    for item in wiki_results:
        key = norm_url(item["url"])
        if key not in seen:
            seen.add(key)
            merged.append(item)

    payload = {
        "query": query,
        "fact": fact,
        "results": merged[:30],
        "sources": sources,
        "google_url": f"https://www.google.com/search?q={quote_plus(query)}",
    }
    CACHE[query.lower()] = (time.time(), payload)
    return payload


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/search")
def api_search():
    q = clean(request.args.get("q", ""))
    if not q:
        return jsonify(error="Type something to search."), 400
    if len(q) > 300:
        return jsonify(error="Search text is too long."), 400
    return jsonify(search_all(q))


@app.get("/health")
def health():
    return jsonify(status="ok", app="websearch", sources=["Bing", "DuckDuckGo", "Brave", "Mojeek", "Wikipedia"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
