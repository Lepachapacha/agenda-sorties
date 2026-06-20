# CLAUDE.md — Agenda Sorties Montpellier
# Projet personnel Nicolas Miras — Lepachapacha
# Dernière mise à jour : 20 juin 2026

---

## CONTEXTE DU PROJET

Page web personnelle listant toutes les sorties culturelles, concerts, festivals,
cinéma, humour, danse latine et activités de la région Montpellier→Nîmes→Sète→Béziers→Marseille.
Hébergée sur GitHub Pages, mise à jour automatique quotidienne via GitHub Actions.

**URL publique :** https://lepachapacha.github.io/agenda-sorties
**Repo :** https://github.com/Lepachapacha/agenda-sorties
**Compte GitHub :** Lepachapacha (compte personnel — NE PAS confondre avec org QG-GIT-CAFES-BIBAL)

---

## STRUCTURE DU PROJET

```
agenda-sorties/
├── CLAUDE.md                  ← ce fichier — contexte pour Claude
├── agenda-config.md           ← SOURCE DE VÉRITÉ — éditer ici les événements manuels
├── sources.md                 ← 51 sources scrapées (agendas, salles, humour, danse...)
├── gemini-queries.md          ← 14 requêtes Google Search Gemini (éditables sans code)
├── scraper.py                 ← couche 2 : RSS → JSON-LD → texte brut
├── gemini_search.py           ← couche 3 : Google Search via Gemini 1.5 Flash
├── generate.py                ← orchestrateur : scrape + Gemini + Claude Sonnet → JSON → HTML
├── template.html              ← template HTML avec placeholders {{EVENTS_JSON}} etc.
├── index.html                 ← page générée — NE PAS éditer à la main
├── requirements.txt           ← anthropic, requests, beautifulsoup4, google-genai
├── scrape_report.json         ← rapport debug du dernier scrape (généré automatiquement)
├── events_extracted.json      ← événements extraits du dernier run (généré automatiquement)
└── .github/
    └── workflows/
        └── update.yml         ← GitHub Actions cron 6h UTC quotidien
```

---

## FICHIER CLÉ : agenda-config.md

Source de vérité pour les événements confirmés manuellement. Priorité absolue sur le scrape.
```
- DATE | TITRE | CATEGORIE | LIEU | NOTE | AVEC_FILS(oui/non) | ETOILES(1-3) | URL | GROUPE
```

Catégories : `festival` `concert` `theatre` `expo` `danse` `jazz` `classique` `electro` `feria` `humour` `activite`

---

## ARCHITECTURE PIPELINE (3 couches)

```
Couche 1 : agenda-config.md       ← manuel, priorité absolue, direct sans Claude
Couche 2 : scraper.py             ← RSS → JSON-LD → texte brut (51 sources)
Couche 3 : gemini_search.py       ← 14 requêtes Google via Gemini 1.5 Flash grounding
                  ↓
          generate.py — cap 120K chars — Claude Sonnet 4.6 → JSON → index.html
```

**Séparation claire dans generate.py :**
- `manual_to_json()` : convertit agenda-config.md directement (sans Claude)
- `build_scraped_events()` : envoie scrape+Gemini à Claude, exclut les titres déjà manuels

---

## SCRAPER (scraper.py)

- **Couche 1 RSS** : registre `RSS_FEEDS` (agendaculturel.fr 34/30/13) + détection auto WordPress `/feed/`
- **Couche 2 JSON-LD** : Schema.org/Event, gère @graph, ItemList, fallback ville via `_city_from_url()`
- **Couche 3 texte** : BeautifulSoup, cap `MAX_CHARS_FALLBACK = 12000`
- **Pas de JS_DOMAINS** : tous les sites tentés (les sites JS retournent peu de contenu mais sans planter)
- **Délai** : 1s entre toutes les requêtes

---

## GEMINI SEARCH (gemini_search.py)

- Modèle : `gemini-1.5-flash` (free tier — search grounding disponible)
- `gemini-2.0-flash` est BLOQUÉ en free tier pour search grounding (`limit: 0`)
- 14 requêtes dans `gemini-queries.md` (fichier éditable sans toucher au code)
- Rate limit free tier : 15 RPM → délai 4s entre requêtes
- Fallback gracieux : si `GEMINI_API_KEY` absent ou 429, retourne `""` et le pipeline continue

---

## GÉNÉRATION (generate.py)

- `max_tokens = 32768` (Claude Sonnet 4.6 supporte 64K — on utilise 50% pour marge)
- Cap input Claude : `MAX_CLAUDE_INPUT = 120_000` chars (~30K tokens)
- **JSON repair** dans `extract_json()` : si Claude tronque sa réponse, récupère les objets complets avant la coupure
- `scrape_report.json` : rapport debug complet par source après chaque run
- `events_extracted.json` : liste des événements extraits + films

---

## TEMPLATE HTML (template.html)

Placeholders injectés par generate.py :
- `{{EVENTS_JSON}}` — tableau JSON des événements
- `{{FILMS_JSON}}` — tableau JSON des films
- `{{SOURCES_JSON}}` — liste des sources
- `{{LAST_UPDATED}}` — date FR du dernier run

**Sections de la page :**
1. Concerts & Festivals (`#concerts`) — cat: festival, concert, jazz, electro, classique, feria
2. Cinéma (`#cinema`) — films cette semaine
3. Expos & Spectacles (`#expos`) — cat: theatre, expo
4. Danse Latine (`#danse`) — cat: danse
5. Humour (`#humour`) — cat: humour
6. Activités Père & Fils (`#activites`) — cat: activite
7. Sorties Permanentes
8. Sources

---

## CINÉMAS SUIVIS

| Cinéma | URL AlloCiné |
|--------|-------------|
| Pathé Odysseum Montpellier | allocine.fr/seance/salle_gen_csalle=P0702.html |
| Mégarama Saint-Gély | allocine.fr/seance/salle_gen_csalle=W4980.html |

---

## GITHUB ACTIONS (update.yml)

- **Cron :** `0 6 * * *` (6h UTC = 8h Paris)
- **Push triggers :** `agenda-config.md`, `sources.md`, `gemini-queries.md`, `scraper.py`, `generate.py`, `gemini_search.py`
- **Secrets requis :**
  ```
  ANTHROPIC_API_KEY   ← Claude Sonnet API
  GEMINI_API_KEY      ← Google AI Studio (free tier)
  ```
- **Gestion conflit rebase :** `git pull --rebase -X ours` (les fichiers générés du bot gagnent toujours)

---

## CONTEXTE PERSONNEL

- **Ville :** Montpellier (Vendargues)
- **Zone couverte :** Nîmes → Montpellier → Sète → Cap d'Agde → Béziers → Marseille (1h15)
- **Fils :** 10 ans — orientation 50/50 sport/culture
- **Danse :** pratique la salsa et la bachata — lieu habituel : Le Temple de la Danse (Montpellier)
- **Événements récurrents prioritaires :**
  - Festival de Nîmes (juin→juillet)
  - Jazz à Sète (juillet)
  - Worldwide Festival Sète (fin juin)
  - Family Piknik / Pérol's Beach (août)
  - Féria de Béziers (août)
  - Festival Radio France Occitanie (juillet)
  - **Tempo Latino** — Vic-Fezensac (Gers), fin juillet — festival salsa incontournable
  - Soirées salsa/bachata (Temple de la Danse + Alma Dance Montpellier)

---

## HISTORIQUE DES SESSIONS

### Session 1 — 19 juin 2026
- Création du projet, recherche festivals été 2026
- Génération index.html v1 + agenda-config.md
- Configuration VS Code + Git + GitHub Pages

### Session 2 — 20 juin 2026 (matin)
- Audit scraper → diagnostic pertes JS-rendered + limite chars
- Réécriture scraper.py pipeline 3 couches RSS → JSON-LD → texte
- Sources étendues : Marseille (Silo, Dôme), humour (JDS humour, Adam Concerts), danse latine
- Sections Danse + Humour ajoutées au template.html
- Passages Haiku → Sonnet 4.6, max_tokens 8192 → 16384

### Session 3 — 20 juin 2026 (après-midi)
- **Diagnostic racine :** scraper passif + sites JS inaccessibles = perte des meilleures sources
- **Architecture hybride RSS + Gemini Search** — 3 couches
- Création `gemini_search.py` (Gemini 1.5 Flash, 14 requêtes thématiques)
- Création `gemini-queries.md` (requêtes éditables)
- Suppression `JS_DOMAINS` — tous les sites tentés, Gemini complète
- Refactorisation generate.py : `manual_to_json()` + `build_scraped_events()` séparés
- Fix conflit rebase Actions : `git pull --rebase -X ours`
- Fix Gemini : `gemini-2.0-flash` → `gemini-1.5-flash` (free tier search grounding)
- Fix JSON tronqué : `max_tokens` 16384 → 32768 + `extract_json()` repair automatique
- Fix input trop grand : cap 120K chars avant envoi à Claude

---

## BUGS CONNUS / POINTS D'ATTENTION

- **AlloCiné** : scrape texte fonctionne (5-6K chars) mais contenu peu structuré — films extraits avec qualité variable
- **Gemini 2.0 Flash** : search grounding BLOQUÉ en free tier (`limit: 0`) — utiliser 1.5 Flash
- **Festival de Nîmes RSS** : ne retourne qu'1 item (feed minimal) — Gemini Search est la vraie source
- **Le Moulin Marseille / Le Dôme** : erreurs réseau intermittentes — sans impact (autres sources couvrent)

---

## PROCHAINES ÉTAPES

- [x] Repo GitHub créé + GitHub Pages actif
- [x] Workflow Actions opérationnel (cron + push triggers)
- [x] ANTHROPIC_API_KEY configuré
- [x] GEMINI_API_KEY configuré
- [x] Architecture hybride 3 couches opérationnelle
- [x] Sections Humour + Danse dans le template
- [x] Correction JSON tronqué + max_tokens
- [ ] **Valider** que les événements scrapés apparaissent sur la page (Gemini 1.5 Flash à tester)
- [ ] **AlloCiné** : améliorer l'extraction films (contenu peu structuré en texte brut)
- [ ] Ajouter flux RSS Paloma officiel (le `/feed/` retourne blog, pas agenda)
- [ ] Vérifier que Gemini 1.5 Flash ne touche pas sa limite free tier (15 RPM, ~1500 req/jour)

---

## COMMANDES UTILES

```bash
# Déclencher un run manuel
# GitHub Actions → Daily agenda update → Run workflow

# Voir ce qui a été extrait
cat events_extracted.json | python -m json.tool | head -100

# Voir le rapport scrape
cat scrape_report.json | python -m json.tool

# Push avec gestion conflit Actions
git pull --rebase -X ours origin main && git push origin main
```

---

## NOTES TECHNIQUES

- Ne jamais commiter sur les repos de l'org QG-GIT-CAFES-BIBAL depuis ce projet
- Le token GitHub est un Fine-grained PAT limité au repo agenda-sorties uniquement
- `index.html` est généré — éditer `agenda-config.md` pour les événements manuels
- `template.html` est la source HTML — éditer `template.html` pour changer la mise en page
