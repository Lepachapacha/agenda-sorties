import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
MAX_CHARS_PER_SOURCE = 4000
TIMEOUT = 12


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


def fetch_text(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        return "\n".join(lines)[:MAX_CHARS_PER_SOURCE]
    except Exception as e:
        return f"[Indisponible : {e}]"


def scrape_all(path="sources.md"):
    sources = parse_sources(path)
    results = []
    for s in sources:
        print(f"  Scraping : {s['name']}")
        text = fetch_text(s["url"])
        results.append(f"=== {s['name']} ({s['url']}) ===\n{text}")
    return "\n\n".join(results)
