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

    # Tentative avec search grounding (nécessite quota suffisant — Workspace Enterprise OK)
    # Fallback sans grounding si quota dépassé
    search_tool = types.Tool(google_search=types.GoogleSearch())
    USE_GROUNDING = True  # désactivé automatiquement sur 429

    # Modèles par ordre de préférence
    MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"]
    model_name = None
    for candidate in MODELS:
        try:
            client.models.generate_content(
                model=candidate,
                contents="test",
                config=types.GenerateContentConfig(
                    tools=[search_tool],
                    response_modalities=["TEXT"],
                ),
            )
            model_name = candidate
            print(f"  [Gemini] Modèle avec grounding : {model_name}")
            break
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"  [Gemini] {candidate} : quota search grounding dépassé")
            elif "404" in err:
                print(f"  [Gemini] {candidate} : modèle non disponible")
            else:
                print(f"  [Gemini] {candidate} : {type(e).__name__}: {err[:80]}")

    if not model_name:
        # Fallback sans grounding
        USE_GROUNDING = False
        model_name = "gemini-2.0-flash-lite"
        print(f"  [Gemini] Fallback sans grounding sur {model_name}")

    results = []
    for i, (label, query) in enumerate(queries):
        print(f"  [Gemini {i+1}/{len(queries)}] {label}")
        try:
            cfg = types.GenerateContentConfig(response_modalities=["TEXT"])
            if USE_GROUNDING:
                cfg = types.GenerateContentConfig(
                    tools=[search_tool],
                    response_modalities=["TEXT"],
                )
                prompt = (
                    "Recherche les informations suivantes et liste de façon exhaustive "
                    "TOUS les événements, artistes, dates, lieux et billetteries trouvés. "
                    "Inclure les noms exacts, les dates, les villes et les URLs disponibles. "
                    f"Requête : {query}"
                )
            else:
                prompt = (
                    "Liste tous les événements culturels, concerts, festivals, spectacles "
                    f"que tu connais pour : {query}. "
                    "Noms exacts, dates 2026, villes, lieux. Format liste, français."
                )
            response = client.models.generate_content(
                model=model_name, contents=prompt, config=cfg,
            )
            text = response.text
            if text and text.strip():
                mode = "grounding" if USE_GROUNDING else "knowledge"
                results.append(f"=== [Gemini/{mode}] {label} ===\n{text.strip()}")
                print(f"    → {len(text)} chars")
            else:
                print("    → Vide")
        except Exception as e:
            err = str(e)[:80]
            print(f"    → Erreur : {type(e).__name__}: {err}")
            if ("429" in err or "RESOURCE_EXHAUSTED" in err) and USE_GROUNDING:
                print("  [Gemini] Quota grounding dépassé — bascule sans grounding")
                USE_GROUNDING = False

        if i < len(queries) - 1:
            time.sleep(4)

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
