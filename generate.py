import json
import os
import re
import sys
from datetime import date
import anthropic
from scraper import parse_sources, scrape_all


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
    # Retire les blocs markdown ```json ... ```
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*',     '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$',     '', text, flags=re.MULTILINE)
    text = text.strip()
    # Extrait le premier tableau JSON trouvé dans la réponse
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def ask_claude(client, prompt, model="claude-sonnet-4-6"):
    msg = client.messages.create(
        model=model,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


def build_events_json(client, manual_events, scraped_content, today):
    manual_text = "\n".join(
        f"- {e['date']} | {e['titre']} | {e['categorie']} | {e['lieu']}"
        + (f" | {e['note']}" if e["note"] else "")
        + (" | fils=oui" if e["fils"] else "")
        + (f" | etoiles={e['etoiles']}")
        + (f" | url={e['url']}" if e["url"] else "")
        + (f" | groupe={e['groupe']}" if e.get("groupe") else "")
        for e in manual_events
        if e["date"] >= today
    )

    prompt = f"""Extrait TOUS les événements culturels mentionnés pour la région Montpellier–Nîmes–Sète–Béziers–Marseille.

ÉVÉNEMENTS CONFIRMÉS (priorité absolue, inclure tels quels sans modification) :
{manual_text}

CONTENU SCRAPÉ DES SOURCES :
{scraped_content}

RÈGLES D'EXTRACTION :
- Zone : Montpellier, Nîmes, Sète, Béziers, Hérault (34), Gard (30), Marseille et alentours (13)
- Période : {today} jusqu'à dans 12 mois
- Être EXHAUSTIF : extraire TOUS les événements identifiables dans le contenu, même si la date est approximative
- En cas de doublon avec les événements confirmés : conserver la version confirmée
- Si la date exacte est inconnue mais que l'événement est réel : utiliser "2099-01-01" pour le signaler
- Ne pas inventer de détails absents du contenu, mais ne pas non plus rejeter des événements par excès de prudence

CATÉGORIES (choisir la plus précise) :
- festival : multi-jours avec plusieurs artistes
- concert : concert unique (rock, pop, rap, chanson, world...)
- jazz : concert jazz ou musiques du monde
- electro : club, DJ set, techno, house
- classique : musique classique, opéra, orchestre
- theatre : pièce de théâtre, spectacle de scène
- expo : exposition, musée, galerie
- danse : spectacle de danse, soirée salsa/bachata, festival dansant
- humour : one-man-show, stand-up, café-théâtre, sketch
- feria : corrida, féria, tauromachie
- activite : loisirs, sport, famille, sortie nature

MAPPING section (obligatoire, choisir exactement une valeur) :
- "concerts"  → cat = festival, concert, jazz, electro, classique, feria
- "expos"     → cat = theatre, expo
- "danse"     → cat = danse
- "humour"    → cat = humour
- "activites" → cat = activite

Retourne UNIQUEMENT un tableau JSON valide (aucun texte avant ou après) :
[
  {{
    "date": "YYYY-MM-DD",
    "titre": "Nom exact de l'événement",
    "cat": "categorie",
    "lieu": "Nom du lieu, Ville",
    "note": "Artiste, description courte — vide si rien",
    "fils": false,
    "stars": 1,
    "section": "concerts|expos|danse|humour|activites",
    "url": "URL directe de l'événement ou billetterie, vide si introuvable",
    "gratuit": false,
    "groupe": ""
  }}
]

Pour "stars" : 3 = incontournable/rare, 2 = très bon, 1 = normal.
Pour "fils" : true uniquement si l'événement est adapté à un enfant de 10 ans.
Pour "url" : utiliser l'URL la plus directe vers la billetterie ou la page de l'événement."""

    raw = ask_claude(client, prompt)
    return extract_json(raw)


def build_films_json(client, scraped_content, today):
    prompt = f"""Extrait les films actuellement à l'affiche au Pathé Odysseum (Montpellier) et au Mégarama Saint-Gély depuis le contenu scrapé.

CONTENU SCRAPÉ :
{scraped_content}

Aujourd'hui : {today}

Retourne UNIQUEMENT un tableau JSON valide :
[
  {{
    "cinema": "pathe|megarama",
    "titre": "Titre du film",
    "meta": "Genre, réalisateur ou acteur principal",
    "famille": true/false
  }}
]

Si aucun film n'est trouvé dans le contenu scrapé, retourne un tableau vide []."""

    raw = ask_claude(client, prompt)
    try:
        return extract_json(raw)
    except Exception:
        return []


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

    print("Scraping des sources...")
    scraped = scrape_all()

    print("Extraction événements (Claude)...")
    try:
        events = build_events_json(client, manual_events, scraped, today)
        print(f"  {len(events)} événements extraits")
    except Exception as e:
        print(f"  ERREUR extraction événements : {e}", file=sys.stderr)
        print("  Fallback : utilisation des événements manuels uniquement")
        events = [
            {
                "date":    ev["date"],
                "titre":   ev["titre"],
                "cat":     ev["categorie"],
                "lieu":    ev["lieu"],
                "note":    ev["note"],
                "fils":    ev["fils"],
                "stars":   ev["etoiles"],
                "section": "activites" if ev["categorie"] == "activite"
                           else ("danse" if ev["categorie"] == "danse"
                           else ("humour" if ev["categorie"] == "humour"
                           else ("expos" if ev["categorie"] in ("expo","theatre")
                           else "concerts"))),
                "url":     ev["url"],
                "gratuit": False,
                "groupe":  ev.get("groupe", ""),
            }
            for ev in manual_events if ev["date"] >= today
        ]

    print("Extraction films (Claude)...")
    try:
        films = build_films_json(client, scraped, today)
        print(f"  {len(films)} films extraits")
    except Exception as e:
        print(f"  ERREUR films : {e}", file=sys.stderr)
        films = []

    sources_list = build_sources_json()

    print("Injection dans template.html...")
    with open("template.html", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{EVENTS_JSON}}",  json.dumps(events,       ensure_ascii=False, indent=2))
    html = html.replace("{{FILMS_JSON}}",   json.dumps(films,        ensure_ascii=False, indent=2))
    html = html.replace("{{SOURCES_JSON}}", json.dumps(sources_list, ensure_ascii=False, indent=2))
    html = html.replace("{{LAST_UPDATED}}", format_date_fr(today))

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html généré avec succès.")


if __name__ == "__main__":
    main()
