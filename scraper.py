import json
import re
import time
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
MAX_CHARS_FALLBACK  = 12000  # texte brut quand pas de JSON-LD
MAX_JSONLD_EVENTS   = 60    # cap par source (évite qu'une source monopolise le contexte)
TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 1.0  # secondes — évite les bans

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


# ── RSS parsing ───────────────────────────────────────────────────────────────

# Flux RSS connus, indexés par domaine → path du feed
RSS_FEEDS = {
    "34.agendaculturel.fr": "/rss",
    "30.agendaculturel.fr": "/rss",
    "13.agendaculturel.fr": "/rss",
}

# Suffixes WordPress standard détectés automatiquement
WP_FEED_SUFFIXES = ("/feed/", "/feed", "?feed=rss2")

# Domaines dont le flux WordPress est un blog de news (pas un agenda) — skip auto-détection RSS
RSS_SKIP_DOMAINS = {"festivaldenimes.com", "almadance.fr"}


def _rss_url_for(url):
    """
    Retourne l'URL du flux RSS si connue ou détectable, sinon None.
    Essaie d'abord le registre RSS_FEEDS, puis les suffixes WordPress.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lstrip("www.")

    # Registre explicite
    for known_domain, feed_path in RSS_FEEDS.items():
        if known_domain in domain:
            return f"{parsed.scheme}://{parsed.netloc}{feed_path}"

    # Domaines dont le flux WordPress est un blog — pas d'agenda, skip
    for skip_domain in RSS_SKIP_DOMAINS:
        if skip_domain in domain:
            return None

    # Détection automatique WordPress (/feed/ en bout d'URL de base)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for suffix in WP_FEED_SUFFIXES:
        candidate = base + suffix
        try:
            r = requests.head(candidate, headers=HEADERS, timeout=6, allow_redirects=True)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ("xml" in ct or "rss" in ct):
                return candidate
        except Exception:
            pass
    return None


def _strip_html(text):
    """Retire les balises HTML d'une chaîne (descriptions RSS)."""
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def fetch_rss(feed_url):
    """
    Récupère et parse un flux RSS. Retourne une chaîne formatée pour Claude.
    Chaque item = une ligne : TITRE | DATE_PUB | URL | DESCRIPTION
    """
    try:
        r = requests.get(feed_url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        if not items:
            return None

        lines = []
        for item in items[:40]:   # cap à 40 items par feed
            title = item.findtext("title", "").strip()
            pub   = item.findtext("pubDate", "")[:16]   # "Fri, 19 Jun 2026"
            link  = item.findtext("link", "").strip()
            desc  = _strip_html(item.findtext("description", ""))[:200]
            lines.append(f"{title} | {pub} | {link} | {desc}")

        return f"[RSS · {len(lines)} items]\n" + "\n".join(lines)
    except Exception:
        return None


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


def _city_from_url(url):
    """Infère la ville principale depuis l'URL source — fallback quand location est vide en JSON-LD."""
    u = url.lower()
    if "montpellier" in u:   return "Montpellier"
    if "nimes" in u:         return "Nîmes"
    if "sete" in u:          return "Sète"
    if "marseille" in u:     return "Marseille"
    if "beziers" in u:       return "Béziers"
    if "34.agenda" in u:     return "Hérault (34)"
    if "30.agenda" in u:     return "Gard (30)"
    if "13.agenda" in u:     return "Marseille (13)"
    return ""


def format_jsonld_event(ev, fallback_city=""):
    """Sérialise un Event JSON-LD en une ligne pipe-séparée pour le prompt Claude."""
    loc = _loc_str(ev.get("location", {})) or fallback_city
    parts = [
        ev.get("name", ""),
        (ev.get("startDate") or ev.get("datePublished") or "")[:10],
        loc,
        (ev.get("description") or "")[:150].replace("\n", " "),
        ev.get("url", "") if str(ev.get("url", "")).startswith("http") else "",
        _price_tag(ev.get("offers", {})),
    ]
    return " | ".join(p for p in parts if p)


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_text(url):
    try:
        # Stratégie 1 : RSS — données structurées si feed connu ou détecté
        rss_url = _rss_url_for(url)
        if rss_url:
            rss_content = fetch_rss(rss_url)
            if rss_content:
                return rss_content

        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Stratégie 2 : JSON-LD — données structurées embarquées dans le HTML
        jsonld_events = extract_jsonld_events(soup)
        if jsonld_events:
            city_hint = _city_from_url(url)
            lines = [format_jsonld_event(ev, fallback_city=city_hint) for ev in jsonld_events]
            return f"[JSON-LD · {len(jsonld_events)} événements]\n" + "\n".join(lines)

        # Stratégie 3 : texte brut (fallback)
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


def _item_count(text, method):
    """Extrait le nombre d'items structurés depuis l'en-tête du contenu."""
    if method == "RSS":
        m = re.search(r'\[RSS · (\d+) items\]', text)
        return int(m.group(1)) if m else 0
    if method == "JSON-LD":
        m = re.search(r'\[JSON-LD · (\d+)', text)
        return int(m.group(1)) if m else 0
    return 0


def scrape_all(path="sources.md"):
    """
    Scrape toutes les sources.
    Retourne (texte_concatene: str, rapport: dict).
    Le rapport contient les stats par source et les totaux — utilisé par generate.py
    pour sauvegarder scrape_report.json.
    """
    sources = parse_sources(path)
    results = []
    report_sources = []
    counts = {"skip": 0, "RSS": 0, "JSON-LD": 0, "texte": 0, "erreur": 0}
    total_items = 0
    total_chars = 0

    for i, s in enumerate(sources):
        print(f"  [{i+1}/{len(sources)}] Scraping : {s['name']}")
        text = fetch_text(s["url"])

        if text.startswith("[JSON-LD"):
            method = "JSON-LD"
        elif text.startswith("[RSS"):
            method = "RSS"
        elif text.startswith("[Skipped"):
            method = "skip"
        elif any(text.startswith(p) for p in ("[Timeout", "[HTTP", "[Indisponible")):
            method = "erreur"
        else:
            method = "texte"

        items = _item_count(text, method)
        chars = len(text)
        counts[method] = counts.get(method, 0) + 1
        total_items += items
        total_chars += chars

        label = f"{method}, {chars} chars" + (f", {items} items" if items else "")
        print(f"    → {label}")

        report_sources.append({
            "name":    s["name"],
            "url":     s["url"],
            "method":  method,
            "items":   items,
            "chars":   chars,
            "preview": text[:100].replace("\n", " "),
        })
        results.append(f"=== {s['name']} ({s['url']}) ===\n{text}")

        time.sleep(DELAY_BETWEEN_REQUESTS)

    rapport = {
        "sources": report_sources,
        "totals": {
            "sources_total":           len(sources),
            "sources_skip":            counts["skip"],
            "sources_rss":             counts["RSS"],
            "sources_jsonld":          counts["JSON-LD"],
            "sources_text":            counts["texte"],
            "sources_erreur":          counts["erreur"],
            "total_items_structured":  total_items,
            "total_chars":             total_chars,
        },
    }
    return "\n\n".join(results), rapport
