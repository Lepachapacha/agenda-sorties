import os
import sys
from datetime import date
import anthropic


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


def generate_html(events, today):
    upcoming = [e for e in events if e["date"] >= today]
    print(f"  {len(events)} events parsed, {len(upcoming)} upcoming")

    client = anthropic.Anthropic()

    events_text = "\n".join(
        f"- {e['date']} | {e['titre']} | {e['categorie']} | {e['lieu']}"
        + (f" | {e['note']}" if e["note"] else "")
        + (" | ⭐" * e["etoiles"])
        + (" | 👦" if e["fils"] else "")
        for e in upcoming
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""Tu génères le <body> d'une page HTML simple listant ces événements à venir.
- Regroupe par mois
- Indique la catégorie et le lieu
- Mets en avant les ⭐⭐⭐ et les événements 👦 (père & fils)
- HTML minimaliste, pas de CSS externe
- Retourne uniquement le HTML du body, rien d'autre

Aujourd'hui : {today}

Événements :
{events_text}"""
        }]
    )

    body = message.content[0].text

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agenda Sorties — Montpellier · Nîmes · Sète</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1.25rem; color: #1a1a2e; }}
    h1 {{ font-size: 1.8rem; margin-bottom: .25rem; }}
    footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: .75rem; color: #888; }}
  </style>
</head>
<body>
{body}
<footer>
  Généré automatiquement le {today} · GitHub Actions + Claude API ·
  <a href="https://github.com/Lepachapacha/agenda-sorties">Source</a>
</footer>
</body>
</html>"""


def main():
    today = date.today().isoformat()
    print(f"[generate.py] {today}")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    events = parse_events()
    html = generate_html(events, today)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("  index.html written")


if __name__ == "__main__":
    main()
