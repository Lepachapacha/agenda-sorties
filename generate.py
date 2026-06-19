import os
import sys
from datetime import date
import anthropic
from scraper import scrape_all


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
                        })
                    except (ValueError, IndexError):
                        pass
    return events


def generate_html(events, scraped_content, today):
    upcoming = [e for e in events if e["date"] >= today]
    print(f"  {len(events)} events dans le fichier, {len(upcoming)} à venir")

    client = anthropic.Anthropic()

    events_text = "\n".join(
        f"- {e['date']} | {e['titre']} | {e['categorie']} | {e['lieu']}"
        + (f" | {e['note']}" if e["note"] else "")
        + (" ⭐" * e["etoiles"])
        + (" 👦" if e["fils"] else "")
        for e in upcoming
    )

    prompt = f"""Tu es un assistant agenda pour la région Montpellier–Nîmes–Sète–Béziers.

═══ ÉVÉNEMENTS CONFIRMÉS (priorité absolue) ═══
{events_text}

═══ CONTENU SCRAPÉ DES SOURCES DU JOUR ═══
{scraped_content}

═══ INSTRUCTIONS ═══
Aujourd'hui : {today}

1. Extrais les événements pertinents du contenu scrapé :
   - Zone géographique : Montpellier, Nîmes, Sète, Béziers, Hérault (34), Gard (30)
   - Période : à partir d'aujourd'hui jusqu'à 3 mois
   - Catégories : concerts, festivals, expos, théâtre, danse, jazz, électro, féria, cinéma, activités famille

2. Fusionne avec les événements confirmés :
   - En cas de doublon, conserve les infos des événements confirmés
   - Ignore les événements dont la date est antérieure à {today}

3. Génère une page HTML complète avec :
   - Dark theme élégant (fond sombre, accents ambrés)
   - Google Fonts : Playfair Display + Inter
   - Sections : Festivals & Concerts / Expos & Spectacles / Activités Père & Fils / Cinéma
   - Chaque événement : date formatée en français, titre, lieu, catégorie (badge coloré)
   - Badge ⭐ sur les incontournables, badge 👦 sur les sorties père & fils
   - Navigation sticky en haut
   - Pied de page : "Généré le {today} · Sources : {len(scraped_content.split('===')) - 1} sites scrapés"
   - Responsive mobile

Retourne uniquement le HTML complet (de <!DOCTYPE html> à </html>), rien d'autre."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def main():
    today = date.today().isoformat()
    print(f"[generate.py] Démarrage — {today}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERREUR : ANTHROPIC_API_KEY non définie", file=sys.stderr)
        sys.exit(1)

    print("Lecture agenda-config.md...")
    events = parse_events()

    print("Scraping des sources...")
    scraped = scrape_all()

    print("Appel Claude API...")
    html = generate_html(events, scraped, today)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html généré avec succès.")


if __name__ == "__main__":
    main()
