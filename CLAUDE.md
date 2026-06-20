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

## MODE DE TRAVAIL AUTONOME (Claude Code)

Claude peut travailler en boucle autonome sur ce projet sans intervention humaine.
Le pipeline est : push → Actions run → git pull → analyse → fix → re-push.

### Protocole de boucle autonome

```
1. Push un fix → déclenche GitHub Actions automatiquement
2. ScheduleWakeup(270s) — cache chaud, run fini dans ce délai
3. git pull --rebase -X ours origin main
4. Lire run.log (commité par Actions) — chercher :
   - [Claude ERREUR API] → erreur API à corriger
   - [Claude raw début] → voir ce que Claude retourne réellement
   - [Gemini] → statut Gemini
5. Lire events_extracted.json → events_count, films_count
6. Critères d'arrêt : events_count >= 50 scrapés ET qualité OK
   (vrais titres, vraies dates 2026, bonnes catégories)
7. Si problème → corriger, push, retour étape 2
```

### Accès aux logs sans gh CLI

`run.log` est commité par Actions après chaque run (ajouté à `git add` dans update.yml).
`git pull` suffit pour tout lire. Pas besoin de gh CLI ni de token API GitHub.

### Seuils de qualité

| Métrique | Minimum acceptable | Excellent |
|----------|-------------------|-----------|
| events scrapés | 50 | 200+ |
| films | 10 | 30+ |
| catégories couvertes | 6/11 | 10/11 |

### Résultat de référence (20 juin 2026)
- **330 events** (29 manuels + 301 scrapés), **32 films**
- Gemini non disponible (quota free tier) → scrape seul suffit
- Festival de Nîmes, Jazz à Sète, Humour (58 events), Danse OK

---

## BUGS RÉSOLUS

| Bug | Symptôme | Cause | Fix |
|-----|----------|-------|-----|
| 0 événements scrapés | events_count=29 (manuels seuls) | `ValueError: Streaming is required` — SDK Anthropic refuse `.create()` quand `max_tokens>=32K` | `client.messages.stream()` + `stream.get_final_text()` |
| JSON tronqué | `Unterminated string` | max_tokens=16384 trop petit | max_tokens=32768 + repair dans `extract_json()` |
| Gemini 429 | `limit: 0` sur gemini-2.0-flash | Search grounding quota=0 free tier | Fallback gracieux, pipeline continue sans Gemini |
| Gemini 404 | `NOT_FOUND for API version v1beta` | gemini-1.5-flash disparu de v1beta avec SDK ≥1.0 | Appel sans search_tool sur gemini-2.0-flash-lite |
| Conflit rebase Actions | push rejeté sur JSON générés | Bot commit + push local en même temps | `git pull --rebase -X ours origin main` |
| Logs invisibles | Erreurs silencieuses | stderr non capturé par `_Tee` | `sys.stderr = _Tee(sys.stderr, _log_file)` |

## BUGS CONNUS / POINTS D'ATTENTION

- **Gemini search grounding** : BLOQUÉ free tier (quota=0 sur 2.0-flash, 404 sur 1.5-flash en v1beta). Clé payante nécessaire pour activer la couche 3.
- **AlloCiné** : scrape texte 5-6K chars mais JS-rendu → films extraits depuis mémoire modèle (qualité variable, parfois hallucinés)
- **Festival de Nîmes RSS** : 1 seul item — couvert par scrape JSON-LD JDS + mémoire Claude
- **Titres génériques** : RSS AgendaCulturel publie parfois "Jour 1", "Ouverture" sans titre artiste

---

## PROCHAINES ÉTAPES

- [x] Repo GitHub créé + GitHub Pages actif
- [x] Workflow Actions opérationnel (cron + push triggers)
- [x] ANTHROPIC_API_KEY configuré
- [x] GEMINI_API_KEY configuré
- [x] Architecture hybride 3 couches opérationnelle
- [x] Sections Humour + Danse dans le template
- [x] Pipeline validé : 330 events + 32 films (20 juin 2026)
- [x] Mode autonome Claude opérationnel (ScheduleWakeup + run.log)
- [ ] **Gemini** : clé avec search grounding (plan payant) pour couvrir sites JS
- [ ] **AlloCiné** : source alternative structurée pour les films
- [ ] Ajouter flux RSS Paloma officiel (le `/feed/` retourne blog, pas agenda)

---

## COMMANDES UTILES

```bash
# Push avec gestion conflit Actions
git pull --rebase -X ours origin main && git push origin main

# Voir les résultats du dernier run
cat run.log | tail -20
cat events_extracted.json | python -m json.tool | head -30

# Analyser la distribution des événements
python -c "
import json
d = json.load(open('events_extracted.json', encoding='utf-8'))
from collections import Counter
print('events:', d['events_count'], '| films:', d['films_count'])
cats = Counter(e['cat'] for e in d['events'])
[print(f'  {c}: {n}') for c,n in sorted(cats.items(), key=lambda x:-x[1])]
"
```

---

## NOTES TECHNIQUES

- Ne jamais commiter sur les repos de l'org QG-GIT-CAFES-BIBAL depuis ce projet
- Le token GitHub est un Fine-grained PAT limité au repo agenda-sorties uniquement
- `index.html` est généré — éditer `agenda-config.md` pour les événements manuels
- `template.html` est la source HTML — éditer `template.html` pour changer la mise en page
- `run.log` est généré à chaque run et commité — source de vérité pour le debug
