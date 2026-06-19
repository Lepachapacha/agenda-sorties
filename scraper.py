import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
MAX_CHARS_PER_SOURCE = 2000
TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 1.0  # secondes — évite les bans

# Sites qui nécessitent JS (Selenium) — on les skip proprement
JS_DOMAINS = (
    "allocine.fr",
    "shotgun.live",
    "ticketmaster.fr",
    "bandsintown.com",
    "songkick.com",
    "ra.co",
    "fnacspectacles.com",
    "francebillet.com",
)


def parse_sources(path="sources.md"):
    sources = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- ") and "|" in line:
                parts = [p.strip() for p in line[2:].split("|")]
                if len(parts) >= 2:
                    sources.append({"name": parts[0], "url": parts[1]})
    return sources


def is_js_only(url):
    return any(domain in url for domain in JS_DOMAINS)


def fetch_text(url):
    if is_js_only(url):
        return f"[Skipped — rendu JS requis, non scrapable avec requests]"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        return "\n".join(lines)[:MAX_CHARS_PER_SOURCE]
    except requests.exceptions.Timeout:
        return f"[Timeout après {TIMEOUT}s]"
    except requests.exceptions.HTTPError as e:
        return f"[HTTP {e.response.status_code}]"
    except Exception as e:
        return f"[Indisponible : {type(e).__name__}]"


def scrape_all(path="sources.md"):
    sources = parse_sources(path)
    results = []
    for i, s in enumerate(sources):
        print(f"  [{i+1}/{len(sources)}] Scraping : {s['name']}")
        text = fetch_text(s["url"])
        results.append(f"=== {s['name']} ({s['url']}) ===\n{text}")
        if not is_js_only(s["url"]):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    return "\n\n".join(results)
