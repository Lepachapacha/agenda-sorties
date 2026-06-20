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

    # Note : search grounding (google_search tool) est bloqué en free tier.
    # On tente sans grounding — Gemini synthétise depuis sa connaissance des événements.
    # Si quota dépassé, fallback gracieux.
    client = genai.Client(api_key=api_key)
    model_name = "gemini-2.0-flash-lite"

    results = []
    for i, (label, query) in enumerate(queries):
        print(f"  [Gemini {i+1}/{len(queries)}] {label}")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=(
                    "Liste de façon exhaustive TOUS les événements culturels, concerts, "
                    "festivals, spectacles humour, soirées danse que tu connais pour : "
                    f"{query}. "
                    "Inclure noms exacts, dates 2026, villes, lieux. "
                    "Répondre en français, format liste."
                ),
            )
            text = response.text
            if text and text.strip():
                results.append(f"=== [Gemini] {label} ===\n{text.strip()}")
                print(f"    → {len(text)} chars")
            else:
                print("    → Vide")
        except Exception as e:
            err = str(e)[:80]
            print(f"    → Erreur : {type(e).__name__}: {err}")
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print("  [Gemini] Quota dépassé — skip restant")
                break

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
