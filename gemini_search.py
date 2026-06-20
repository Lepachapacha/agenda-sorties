import os
import time


def run_gemini_searches(queries_path="gemini-queries.md"):
    """
    Lance des recherches Google ciblées via Gemini 2.0 Flash (grounding).
    Retourne le texte consolidé, ou "" si GEMINI_API_KEY est absent ou si une erreur survient.
    Fallback gracieux : le pipeline continue avec le contenu scrapé seul.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  [Gemini] GEMINI_API_KEY non définie — skip")
        return ""

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("  [Gemini] google-genai non installé — skip")
        return ""

    queries = _parse_queries(queries_path)
    if not queries:
        print("  [Gemini] Aucune requête dans gemini-queries.md — skip")
        return ""

    client = genai.Client(api_key=api_key)
    search_tool = types.Tool(google_search=types.GoogleSearch())

    results = []
    for i, (label, query) in enumerate(queries):
        print(f"  [Gemini {i+1}/{len(queries)}] {label}")
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=(
                    "Recherche les informations suivantes et liste de façon exhaustive "
                    "TOUS les événements, artistes, dates, lieux et billetteries trouvés. "
                    "Inclure les noms exacts, les dates, les villes et les URLs disponibles. "
                    f"Requête : {query}"
                ),
                config=types.GenerateContentConfig(
                    tools=[search_tool],
                    response_modalities=["TEXT"],
                ),
            )
            text = response.text
            if text and text.strip():
                results.append(f"=== [Gemini Search] {label} ===\n{text.strip()}")
                print(f"    → {len(text)} chars")
            else:
                print("    → Vide")
        except Exception as e:
            print(f"    → Erreur : {type(e).__name__}: {e}")

        if i < len(queries) - 1:
            time.sleep(4)  # free tier : 15 RPM → 4 s entre chaque requête

    return "\n\n".join(results)


def _parse_queries(path):
    """Parse gemini-queries.md, retourne une liste de (label, requête)."""
    queries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ") and "|" in line:
                    parts = [p.strip() for p in line[2:].split("|", 1)]
                    if len(parts) == 2 and parts[1]:
                        queries.append((parts[0], parts[1]))
    except FileNotFoundError:
        pass
    return queries
