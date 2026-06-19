import json
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
MAX_CHARS_FALLBACK  = 6000  # texte brut quand pas de JSON-LD
MAX_JSONLD_EVENTS   = 60    # cap par source (évite qu'une source monopolise le contexte)
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


# ── JSON-LD extraction ────────────────────────────────────────────────────────

def _is_event(item):
    t = item.get("@type", "")
    types = t if isinstance(t, list) else [t]
    return any("Event" in str(x) for x in types)


def extract_jsonld_events(soup):
    """
    Cherche tous les blocs <script type="application/ld+json"> dans la page.
    Retourne une liste de dicts Event Schema.org (MusicEvent, TheaterEvent, etc.).
    Gère : objet simple, tableau, wrapper @graph, ItemList.
    """
    events = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue

            # Déplie @graph (WordPress / Yoast SEO)
            if "@graph" in item:
                for node in item["@graph"]:
                    if isinstance(node, dict) and _is_event(node):
                        events.append(node)
                continue

            # Déplie ItemList / EventSeries
            if item.get("@type") in ("ItemList", "EventSeries"):
                for entry in item.get("itemListElement", []):
                    obj = entry.get("item", entry) if isinstance(entry, dict) else entry
                    if isinstance(obj, dict) and _is_event(obj):
                        events.append(obj)
                continue

            if _is_event(item):
                events.append(item)

    return events[:MAX_JSONLD_EVENTS]


def _loc_str(loc):
    if isinstance(loc, str):
        return loc.strip()
    if not isinstance(loc, dict):
        return ""
    name = loc.get("name", "")
    addr = loc.get("address", {})
    city = addr.get("addressLocality", "") if isinstance(addr, dict) else str(addr)
    return f"{name}, {city}".strip(", ") if city else name.strip()


def _price_tag(offers):
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return ""
    return "GRATUIT" if str(offers.get("price", "")).strip() in ("0", "0.0") else ""


def format_jsonld_event(ev):
    """Sérialise un Event JSON-LD en une ligne pipe-séparée pour le prompt Claude."""
    parts = [
        ev.get("name", ""),
        (ev.get("startDate") or ev.get("datePublished") or "")[:10],
        _loc_str(ev.get("location", {})),
        (ev.get("description") or "")[:150].replace("\n", " "),
        ev.get("url", "") if str(ev.get("url", "")).startswith("http") else "",
        _price_tag(ev.get("offers", {})),
    ]
    return " | ".join(p for p in parts if p)


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_text(url):
    if is_js_only(url):
        return "[Skipped — rendu JS requis, non scrapable avec requests]"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Stratégie 1 : JSON-LD — données structurées, 0 perte d'info
        jsonld_events = extract_jsonld_events(soup)
        if jsonld_events:
            lines = [format_jsonld_event(ev) for ev in jsonld_events]
            return f"[JSON-LD · {len(jsonld_events)} événements]\n" + "\n".join(lines)

        # Stratégie 2 : texte brut (fallback pour les sites sans JSON-LD)
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        return "\n".join(lines)[:MAX_CHARS_FALLBACK]

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
        method = "JSON-LD" if text.startswith("[JSON-LD") else ("skip" if text.startswith("[Skipped") else "texte")
        print(f"    → {method}, {len(text)} chars")
        results.append(f"=== {s['name']} ({s['url']}) ===\n{text}")
        if not is_js_only(s["url"]):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    return "\n\n".join(results)
