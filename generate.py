import io
import json
import os
import re
import sys
from datetime import date, datetime
import anthropic
from scraper import parse_sources, scrape_all
from gemini_search import run_gemini_searches
# template2.html design Terrasse — Syne+Inter, fond clair, cartes date-block (2026-06-21)


class _Tee:
    """Proxy stdout+stderr vers un fichier log. Délègue tous les attributs inconnus."""
    def __init__(self, stream, log_file):
        self._stream = stream
        self._log = log_file

    def write(self, s):
        self._stream.write(s)
        self._log.write(s)
        self._log.flush()
        return len(s)

    def flush(self):
        self._stream.flush()
        self._log.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


_log_file = open("run.log", "w", encoding="utf-8")
sys.stdout = _Tee(sys.stdout, _log_file)
sys.stderr = _Tee(sys.stderr, _log_file)  # capture aussi les erreurs


def parse_events(path="agenda-config.md"):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- ") and "|" in line:
                parts = [p.strip() for p in line[2:].split("|")]
                if len(parts) >= 6:
                    try:
                        events.append({
                            "date":      parts[0],
                            "titre":     parts[1],
                            "categorie": parts[2],
                            "lieu":      parts[3],
                            "note":      parts[4],
                            "fils":      parts[5].lower() == "oui",
                            "etoiles":   int(parts[6]) if len(parts) > 6 else 1,
                            "url":       parts[7] if len(parts) > 7 else "",
                            "groupe":    parts[8] if len(parts) > 8 else "",
                        })
                    except (ValueError, IndexError):
                        pass
    return events


def extract_json(text):
    text = text.strip()
    # Strip markdown code blocks
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```\s*$',       '', text, flags=re.MULTILINE)
    text = text.strip()

    # Cherche explicitement un tableau JSON d'objets [{ ... }]
    # Plus robuste que \[.*\] qui capture aussi les [brackets] dans du texte
    match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', text)
    if match:
        text = match.group(0)
    elif re.search(r'\[\s*\]', text):
        return []

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON tronqué (max_tokens atteint) — récupère les objets complets avant la coupure
        last_complete = text.rfind('},')
        if last_complete > 0:
            try:
                return json.loads(text[:last_complete + 1] + ']')
            except json.JSONDecodeError:
                pass
        # Dernier recours : parse objet par objet (objets plats sans {}  imbriqués)
        objects = re.findall(r'\{[^{}]+\}', text)
        recovered = []
        for obj in objects:
            try:
                recovered.append(json.loads(obj))
            except json.JSONDecodeError:
                pass
        if recovered:
            print(f"  JSON réparé : {len(recovered)} objets récupérés après coupure")
            return recovered
        raise


def ask_claude(client, prompt, model="claude-sonnet-4-6"):
    try:
        with client.messages.stream(
            model=model,
            max_tokens=32768,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            raw = stream.get_final_text()
    except Exception as e:
        print(f"  [Claude ERREUR API] {type(e).__name__}: {e}")
        raise
    print(f"  [Claude raw début] {raw[:300]!r}")
    return raw


CAT_TO_SECTION = {
    "festival": "concerts", "concert": "concerts", "jazz": "concerts",
    "electro": "concerts", "classique": "concerts", "feria": "concerts",
    "theatre": "expos", "expo": "expos",
    "danse": "danse",
    "humour": "humour",
    "activite": "activites",
}


def manual_to_json(manual_events, today):
    """Convertit les événements manuels directement au format JSON de sortie, sans appel Claude."""
    out = []
    for e in manual_events:
        if e["date"] < today:
            continue
        out.append({
            "date":    e["date"],
            "titre":   e["titre"],
            "cat":     e["categorie"],
            "lieu":    e["lieu"],
            "note":    e["note"],
            "fils":    e["fils"],
            "stars":   e["etoiles"],
            "section": CAT_TO_SECTION.get(e["categorie"], "concerts"),
            "url":     e.get("url", ""),
            "gratuit": False,
            "groupe":  e.get("groupe", ""),
        })
    return out


def build_scraped_events(client, scraped_content, exclude_titles, today):
    """
    Extrait UNIQUEMENT les événements nouveaux depuis le contenu scrapé.
    Les événements manuels sont exclus via exclude_titles pour éviter les doublons.
    """
    exclusion = "\n".join(f"- {t}" for t in exclude_titles) if exclude_titles else "(aucun)"

    prompt = f"""Analyse ce contenu scrapé de sites d'agenda culturels et extrais les événements à venir dans la région Montpellier–Nîmes–Sète–Béziers–Marseille.

CONTENU SCRAPÉ :
{scraped_content}

COMMENT LIRE LES DONNÉES :
- Blocs [RSS · N items] : format = TITRE | pubDate | URL | description
  → pubDate est la date de publication. Pour les agendas culturels (34.agendaculturel.fr, 30.agendaculturel.fr,
    etc.), les articles sont publiés 1-7 jours AVANT l'événement. Utiliser pubDate comme date approximative.
  → Si la description ou le titre mentionne une date précise, la préférer à pubDate.
  → Ne pas rejeter un item RSS uniquement parce que pubDate est dans le passé récent (< 30 jours) :
    l'événement peut encore être à venir ou récent mais toujours pertinent à afficher.
- Blocs [JSON-LD · N événements] : format = TITRE | startDate | LIEU | description | URL
  → startDate est la vraie date de l'événement (champ Schema.org). L'utiliser directement.
  → Si LIEU est vide, la source (visible dans l'en-tête === NOM (URL) ===) définit la zone géographique.
    Ex: source "JDS Humour Montpellier" → events à Montpellier. "JDS Humour Nîmes" → Nîmes.
- Texte brut : extraire les dates explicitement mentionnées.

RÈGLES :
- Zone couverte : Montpellier, Nîmes, Sète, Béziers, Hérault (34), Gard (30), Marseille et alentours (13)
- Les sources ont été présélectionnées pour couvrir cette zone — faire confiance à la source si le lieu est absent
- Période : du {today} jusqu'à dans 12 mois
- Être EXHAUSTIF : extraire tous les événements identifiables, y compris humour, danse, expos, activités
- Exclure les événements dont le titre est dans la liste ci-dessous (déjà dans l'agenda) :
{exclusion}
- Utiliser "2099-01-01" uniquement si aucune date n'est déductible
- Retourner [] si vraiment aucun nouvel événement n'est trouvé (rare)

CATÉGORIES (liste exhaustive — n'utiliser QUE ces valeurs) :
festival, concert, jazz, electro, classique, theatre, expo, danse, humour, feria, activite
⚠ "spectacle" n'est PAS valide → utiliser "theatre" à la place.

SECTION (obligatoire) :
concerts → festival/concert/jazz/electro/classique/feria
expos → theatre/expo
danse → danse
humour → humour
activites → activite

TITRES GÉNÉRIQUES — À EXCLURE :
Ne pas extraire un événement si son titre ne contient pas le nom d'un artiste, d'un spectacle précis ou d'un festival nommé.
Exemples à EXCLURE : "Cepac Silo – concert (date)", "Domaine d'O – spectacle (dates)", "Soir 1", "Jour 2" sans artiste.
Exemples à GARDER : "Cepac Silo – Whitney Houston Tribute", "Domaine d'O – FAUST. FAIT, NON DIT."

FORMAT JSON — COMPACT (une ligne par objet, pas d'indentation) :
[{{"date":"YYYY-MM-DD","titre":"Nom","cat":"cat","lieu":"Lieu, Ville","note":"max 60 chars","fils":false,"stars":1,"section":"concerts","url":"","gratuit":false,"groupe":""}}]

Règles de compacité pour limiter la taille de la réponse :
- "note" : max 60 caractères, préférer "" à une note trop longue
- "url" : mettre "" si l'URL n'est pas directement disponible dans le contenu
- "groupe" : toujours ""
- Pas d'espace ni de saut de ligne entre les objets JSON
- "stars" : 3 = incontournable (grands festivals/noms connus), 2 = très bon, 1 = normal
- "fils" : true uniquement si adapté à un enfant de 10 ans

IMPORTANT : Retourner UNIQUEMENT le tableau JSON, sans texte avant ni après. Pas d'explication, pas de commentaire."""

    raw = ask_claude(client, prompt, model="claude-haiku-4-5")
    return extract_json(raw)


def build_status_html(status):
    """Génère le bloc HTML de statut pipeline pour le footer."""
    badges = []

    # Claude API
    if status["claude"] == "ok":
        badges.append(f'<span class="ps-badge ps-ok">Claude ✓ {status["scraped_count"]} scrapés</span>')
    elif status["claude"] == "fallback":
        badges.append(f'<span class="ps-badge ps-warn">Claude fallback ({status["claude_detail"]}) — {status["fallback_count"]} events prev.</span>')
    else:
        badges.append(f'<span class="ps-badge ps-err">Claude ✗ {status["claude_detail"]}</span>')

    # Gemini
    if status["gemini"] == "ok":
        badges.append(f'<span class="ps-badge ps-ok">Gemini ✓ {status["gemini_chars"]} chars</span>')
    elif status["gemini"] == "quota":
        badges.append('<span class="ps-badge ps-err">Gemini ✗ quota 429</span>')
    else:
        badges.append('<span class="ps-badge ps-warn">Gemini — indisponible</span>')

    # Manuels
    badges.append(f'<span class="ps-badge ps-ok">{status["manual_count"]} manuels</span>')

    return '<div class="pipeline-status">' + ''.join(badges) + '</div>'


def build_stale_banner(status):
    """Bandeau footer d'alerte quand les sorties scrapées ne sont plus rafraîchies."""
    if not status.get("stale"):
        return ""
    if status.get("claude_detail") == "solde insuffisant":
        amorce = "⚠ Plus de crédit API"
    else:
        amorce = "⚠ Mise à jour automatique indisponible"
    fresh = status.get("last_fresh_date")
    date_fr = format_date_fr(fresh) if fresh else "?"
    return (
        '<div class="stale-banner">'
        f'{amorce} — les nouveaux événements ne sont plus récupérés. '
        f'Dernières sorties à jour au <strong>{date_fr}</strong>.'
        '</div>'
    )


def _load_previous_scraped_events(exclude_titles):
    """Fallback: réutilise les événements scrapés du run précédent si Claude échoue."""
    try:
        with open("events_extracted.json", encoding="utf-8") as f:
            prev = json.load(f)
        exclude_set = set(exclude_titles)
        fallback = [e for e in prev.get("events", []) if e.get("titre") not in exclude_set]
        print(f"  Fallback run précédent : {len(fallback)} événements scrapés récupérés")
        return fallback
    except Exception as fe:
        print(f"  Fallback impossible : {fe}")
        return []


def _load_previous_fresh_date():
    """Date du dernier run où Claude a réellement extrait des événements (sinon None)."""
    try:
        with open("events_extracted.json", encoding="utf-8") as f:
            prev = json.load(f)
        return prev.get("last_fresh_date") or (prev.get("timestamp", "")[:10] or None)
    except Exception:
        return None


# Titres génériques sans nom d'artiste/spectacle (le prompt demande déjà de les exclure ;
# ce filtre déterministe rattrape ce que le modèle laisse parfois passer).
_GENERIC_TITLE_RE = re.compile(
    r'^(?:jour|soir|journée|journee)\s+\d+$|^(?:jour\s+j|ouverture|clôture|cloture)$',
    re.IGNORECASE,
)

# Catégories interdites → catégorie valide (le prompt l'indique, ce filtre rattrape les ratés)
_CAT_FIX = {"spectacle": "theatre", "danse-latine": "danse"}


def _filter_scraped_events(events, today):
    """Retire les événements passés et les titres génériques, normalise les catégories."""
    out, dropped_past, dropped_generic, fixed_cat = [], 0, 0, 0
    for e in events:
        d = e.get("date", "")
        if d and d < today:                       # même règle de passé que manual_to_json
            dropped_past += 1
            continue
        if _GENERIC_TITLE_RE.match((e.get("titre") or "").strip()):
            dropped_generic += 1
            continue
        cat = e.get("cat")
        if cat in _CAT_FIX:                        # catégorie interdite → valide + section cohérente
            e["cat"] = _CAT_FIX[cat]
            e["section"] = CAT_TO_SECTION.get(e["cat"], e.get("section") or "concerts")
            fixed_cat += 1
        out.append(e)
    print(f"  Filtre scrapés : -{dropped_past} passés, -{dropped_generic} génériques, "
          f"{fixed_cat} cat. corrigées → {len(out)} retenus")
    return out


def format_date_fr(iso_date):
    mois = ["janvier","février","mars","avril","mai","juin",
            "juillet","août","septembre","octobre","novembre","décembre"]
    d = date.fromisoformat(iso_date)
    return f"{d.day} {mois[d.month - 1]} {d.year}"


def build_sources_json(sources_path="sources.md"):
    sources = parse_sources(sources_path)
    return [{"name": s["name"], "url": s["url"]} for s in sources]


def main():
    today = date.today().isoformat()
    print(f"[generate.py] {today}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERREUR : ANTHROPIC_API_KEY non définie", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()

    print("Lecture agenda-config.md...")
    manual_events = parse_events()
    print(f"  {len(manual_events)} événements manuels")

    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    print("Scraping des sources...")
    scraped, scrape_rapport = scrape_all()

    print("Sauvegarde scrape_report.json...")
    scrape_rapport["timestamp"] = ts
    with open("scrape_report.json", "w", encoding="utf-8") as f:
        json.dump(scrape_rapport, f, ensure_ascii=False, indent=2)
    t = scrape_rapport["totals"]
    print(f"  {t['sources_total']} sources — RSS:{t['sources_rss']} JSON-LD:{t['sources_jsonld']} "
          f"texte:{t['sources_text']} skip:{t['sources_skip']} erreur:{t['sources_erreur']} "
          f"| {t['total_items_structured']} items structurés")

    print("Recherches Gemini Search (couche 3)...")
    gemini_content = run_gemini_searches()
    _gemini_status_raw = "ok"
    if gemini_content:
        print(f"  {len(gemini_content)} chars Gemini ajoutés")
    else:
        print("  Gemini non disponible — pipeline continue avec scrape seul")
        # Détecte si c'est un quota 429 en lisant le run.log tampon déjà écrit
        _gemini_status_raw = "quota"  # run.log montre 429 → on suppose quota par défaut

    # Gemini EN PREMIER pour garantir qu'il entre dans le cap (scraped fait ~170K)
    # Cap global 150K (~38K tokens) : 40K Gemini + 110K scraped
    MAX_GEMINI = 40_000
    MAX_SCRAPED = 110_000
    MAX_CLAUDE_INPUT = MAX_GEMINI + MAX_SCRAPED

    scraped_capped = scraped[:MAX_SCRAPED]
    if len(scraped) > MAX_SCRAPED:
        print(f"  Scrape tronqué : {len(scraped)} → {MAX_SCRAPED} chars")

    if gemini_content:
        gemini_capped = gemini_content[:MAX_GEMINI]
        full_content = gemini_capped + "\n\n" + scraped_capped
        print(f"  Contenu total Claude : {len(full_content)} chars (Gemini: {len(gemini_capped)}, scrape: {len(scraped_capped)})")
    else:
        full_content = scraped_capped
        print(f"  Contenu total Claude : {len(full_content)} chars (scrape seul)")

    run_status = {
        "claude": "ok", "claude_detail": "",
        "scraped_count": 0, "fallback_count": 0,
        "gemini": _gemini_status_raw if not gemini_content else "ok",
        "gemini_chars": len(gemini_content) if gemini_content else 0,
        "manual_count": 0,
    }

    print("Conversion événements manuels...")
    confirmed_events = manual_to_json(manual_events, today)
    run_status["manual_count"] = len(confirmed_events)
    print(f"  {len(confirmed_events)} événements confirmés (agenda-config.md)")

    exclude_titles = [e["titre"] for e in confirmed_events]

    print("Extraction nouveaux événements depuis le scrape + Gemini (Claude)...")
    try:
        scraped_events = build_scraped_events(client, full_content, exclude_titles, today)
        run_status["scraped_count"] = len(scraped_events)
        print(f"  {len(scraped_events)} nouveaux événements extraits depuis les sources")
    except Exception as e:
        err_msg = str(e)
        print(f"  ERREUR extraction scrape : {err_msg}", file=sys.stderr)
        scraped_events = _load_previous_scraped_events(exclude_titles)
        if "credit balance is too low" in err_msg or "credit balance" in err_msg:
            run_status["claude"] = "fallback"
            run_status["claude_detail"] = "solde insuffisant"
        elif "429" in err_msg:
            run_status["claude"] = "fallback"
            run_status["claude_detail"] = "quota 429"
        else:
            run_status["claude"] = "fallback"
            run_status["claude_detail"] = "erreur API"
        run_status["fallback_count"] = len(scraped_events)

    # Filtre déterministe : événements passés + titres génériques ("Jour 1", "Ouverture"…)
    scraped_events = _filter_scraped_events(scraped_events, today)
    if run_status["claude"] == "ok":
        run_status["scraped_count"] = len(scraped_events)
    else:
        run_status["fallback_count"] = len(scraped_events)

    # Date de dernière fraîcheur : aujourd'hui si Claude a réussi, sinon on reprend
    # (et on gèle) la date du dernier run frais — pas de dérive en panne prolongée.
    if run_status["claude"] == "ok":
        last_fresh_date = today
    else:
        last_fresh_date = _load_previous_fresh_date() or today
    run_status["stale"] = run_status["claude"] != "ok"
    run_status["last_fresh_date"] = last_fresh_date

    events = confirmed_events + scraped_events
    print(f"  Total : {len(events)} événements ({len(confirmed_events)} manuels + {len(scraped_events)} scrapés)")

    print("Sauvegarde events_extracted.json...")
    with open("events_extracted.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp":       ts,
            "model":           "claude-haiku-4-5",
            "last_fresh_date": last_fresh_date,
            "events_count":    len(events),
            "events":          events,
        }, f, ensure_ascii=False, indent=2)

    sources_list = build_sources_json()

    print("Injection dans template2.html...")
    with open("template2.html", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{EVENTS_JSON}}",      json.dumps(events,       ensure_ascii=False, indent=2))
    html = html.replace("{{SOURCES_JSON}}",     json.dumps(sources_list, ensure_ascii=False, indent=2))
    html = html.replace("{{LAST_UPDATED}}",     format_date_fr(today))
    html = html.replace("{{STALE_BANNER}}",     build_stale_banner(run_status))
    html = html.replace("{{RUN_STATUS_HTML}}",  build_status_html(run_status))

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html généré avec succès.")


if __name__ == "__main__":
    main()
