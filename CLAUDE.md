# CLAUDE.md — Agenda Sorties Montpellier
# Projet personnel Nicolas Miras — Lepachapacha
# Dernière mise à jour : 21 juin 2026 (session 7)

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
├── sources.md                 ← 47 sources actives + 4 backup JS commentés
├── sources-enrichi.md         ← 92 sources enrichies (généré par agent-recherche-sources)
├── gemini-queries.md          ← 14 requêtes Google Search Gemini (éditables sans code)
├── scraper.py                 ← couche 2 : RSS → JSON-LD → texte brut
├── gemini_search.py           ← couche 3 : Google Search via Gemini 1.5 Flash
├── generate.py                ← orchestrateur : scrape + Gemini + Claude Haiku 4.5 → JSON → HTML
├── template.html              ← template v1 (dark, Playfair Display) — conservé en backup
├── template2.html             ← template v2 ACTIF (Terrasse — Syne+Inter, fond clair, date-block)
├── index.html                 ← page générée — NE PAS éditer à la main
├── requirements.txt           ← anthropic, requests, beautifulsoup4, google-genai
├── run.log                    ← logs du dernier run (généré + commité par Actions)
├── scrape_report.json         ← rapport debug du dernier scrape (généré automatiquement)
├── events_extracted.json      ← événements extraits du dernier run (généré automatiquement)
├── agent-qc-contenu.md        ← prompt agent QC pipeline (compare scrape→extraction→page)
├── agent-recherche-sources.md ← prompt agent recherche de nouvelles sources
├── UX-AGENT.md                ← persona UX/UI pour décisions design
└── .github/
    └── workflows/
        └── update.yml         ← GitHub Actions : cron 6h UTC + run manuel (pas de push trigger)
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
Couche 2 : scraper.py             ← RSS → JSON-LD → texte brut (47 sources)
Couche 3 : gemini_search.py       ← 14 requêtes Google via Gemini 1.5 Flash grounding
                  ↓
          generate.py — cap 150K chars — Claude Haiku 4.5 → JSON → index.html
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

- **1 seul appel Claude par run** : `build_scraped_events()` en **Claude Haiku 4.5** (`claude-haiku-4-5`, $1/$5 par M — 3× moins cher que Sonnet). L'extraction films/cinéma a été supprimée (session 7).
- `max_tokens = 32768` (Haiku 4.5 supporte 64K — on utilise 50% pour marge)
- Cap input Claude : `MAX_GEMINI = 40_000` + `MAX_SCRAPED = 110_000` = 150K chars (~38K tokens) — **non cappé davantage** (couverture max)
- **JSON repair** dans `extract_json()` : si Claude tronque sa réponse, récupère les objets complets avant la coupure
- `scrape_report.json` : rapport debug complet par source après chaque run
- `events_extracted.json` : liste des événements extraits (plus de films)

---

## TEMPLATES HTML

`generate.py` utilise actuellement **`template2.html`** (actif depuis session 5).
`template.html` conservé en backup (dark theme, Playfair Display).

Placeholders injectés par generate.py :
- `{{EVENTS_JSON}}` — tableau JSON des événements
- `{{SOURCES_JSON}}` — liste des sources
- `{{LAST_UPDATED}}` — date FR du dernier run
(le placeholder `{{FILMS_JSON}}` a été retiré en session 7 — plus d'extraction films)

### template2.html — Design « Dark Méditerranéen » (ACTIF)
- **Fonts :** Playfair Display 700/900 (titres événements) + Inter (corps) + Space Mono (dates/labels)
- **Palette :** fond `#0D0B09` (chaud presque-noir), surface `#1C1915`, accent amber `#F59E0B`, urgence coral `#F97316`
- **Hero cards ★★★ :** full-width, gradient violet `#2D1B5C` → bordeaux `#6B1F40`
- **Cartes standard :** date amber Space Mono (petite ligne), titre Playfair Display comme élément principal
- **Vue liste** défaut pour Humour + Activités (toggle ⊞/☰ disponible)
- **Concerts** groupés par mois avec séparateurs amber Space Mono
- Conforme à `UX-AGENT.md` : dark mode méditerranéen, Playfair+Space Mono, hiérarchie Hero/Standard/Dense

### template.html — Design v1 (BACKUP)
- Dark theme : `--bg: #08080c`, accent violet `#818cf8`
- Fonts : Playfair Display + Inter + Space Mono

**Sections communes des deux templates :**
1. Ce Weekend (`#weekend`) — green accent, événements Sam+Dim
2. Concerts & Festivals (`#concerts`) — cat: festival, concert, jazz, electro, classique, feria
3. Cinéma (`#cinema`) — 2 liens AlloCiné (Pathé Odysseum + Mégarama), plus d'extraction films
4. Expos & Spectacles (`#expos`) — cat: theatre, expo
5. Danse Latine (`#danse`) — cat: danse
6. Humour (`#humour`) — cat: humour
7. Activités Père & Fils (`#activites`) — cat: activite
8. Sorties Permanentes
9. Sources

---

## CINÉMAS SUIVIS

| Cinéma | URL AlloCiné |
|--------|-------------|
| Pathé Odysseum Montpellier | allocine.fr/seance/salle_gen_csalle=P0702.html |
| Mégarama Saint-Gély | allocine.fr/seance/salle_gen_csalle=W4980.html |

---

## GITHUB ACTIONS (update.yml)

- **Cron :** `0 6 * * *` (6h UTC = 8h Paris)
- **Déclencheurs :** `schedule` (cron) + `workflow_dispatch` (run manuel). **Triggers `push` retirés (session 7)** — un push de code ne relance plus de run payant ; itérer en local (`python generate.py`) puis lancer manuellement (Actions → Run workflow).
- **Secrets requis :**
  ```
  ANTHROPIC_API_KEY   ← Claude Haiku API
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
- Architecture hybride RSS + Gemini Search — 3 couches
- Création `gemini_search.py` + `gemini-queries.md`
- Suppression `JS_DOMAINS`, cap input 120K→150K, Gemini (40K) avant scraped (110K)
- Fix conflit rebase Actions : `git pull --rebase -X ours`
- Fix JSON tronqué : max_tokens 32768 + repair dans `extract_json()`

### Session 4 — 20 juin 2026 (soir) — VALIDATION PIPELINE
- **Boucle autonome** : mode push→ScheduleWakeup→git pull→run.log→fix→loop
- **Bug critique résolu** : `ValueError: Streaming is required` → fix `client.messages.stream()` + `stream.get_final_text()`
- **Logging** : `run.log` capturant stdout+stderr commité par Actions à chaque run
- **Gemini** : search grounding bloqué free tier → fallback gracieux. Fix : activer facturation sur clé `...Pt9Q`
- **Résultat validé** : **330 events (29 manuels + 301 scrapés) + 32 films** ✅
- **QC agent** : 4 fixes — catégorie "spectacle" interdite, 23 titres génériques exclus, 4 sources mortes commentées, +1 requête Temple de la Danse

### Session 5 — 21 juin 2026 (matin) — 1ER REDESIGN (rejeté)
- `template2.html` v1 « Terrasse » — light mode, Syne+Inter, cartes date-block gauche 62px
- generate.py switché template.html → template2.html, déployé et validé pipeline
- **Rejeté** : date-block dominant = mauvaise hiérarchie, le chiffre du jour écrase le titre

### Session 6 — 21 juin 2026 (après-midi) — REDESIGN DARK MÉDITERRANÉEN
- `template2.html` v2 — dark mode warm conforme UX-AGENT.md
- **Typographie** : Playfair Display (titres) + Space Mono (dates/labels) + Inter (corps)
- **Palette** : fond `#0D0B09`, amber `#F59E0B`, coral `#F97316`, hero gradient violet→bordeaux
- **Hiérarchie cartes** : titre Playfair Display = élément principal, date = petite ligne amber
- **Hero ★★★** : full-width, gradient violet `#2D1B5C` → bordeaux `#6B1F40`
- **Vue liste** défaut humour + activités, concerts groupés par mois

### Session 7 — 21 juin 2026 — OPTIMISATION COÛT API
- **Constat** : ~20 $ sur 2 jours sur la Console API (paiement à l'usage), dus à ~35 runs/jour du pipeline (chaque `push` relançait Actions + boucle autonome). Claude Code est sur **abonnement** (0 $ à l'usage) → 100 % du coût venait du pipeline.
- **`update.yml`** : triggers `push` retirés (cron + `workflow_dispatch` seuls) → ÷~35 sur le nombre de runs.
- **`generate.py`** : extraction événements Sonnet 4.6 → **Haiku 4.5** (3× moins cher). **Tout le cinéma supprimé** (`build_films_json` était un 2ᵉ appel Claude qui envoyait le scrape COMPLET et hallucinait les films).
- **`template2.html`** : section Cinéma = 2 liens statiques AlloCiné (Pathé `P0702`, Mégarama `W4980`) ; JS films nettoyé.
- **Résultat attendu** : ~17 $/j → **~0,11 $/j (~3,5 €/mois)**. Input NON cappé (150K conservés).
- **Garde-fou** : si la qualité Haiku chute (< ~200 events), repasser `build_scraped_events` en `claude-sonnet-4-6` (1 ligne).

---

## MODE DE TRAVAIL AUTONOME (Claude Code)

Claude peut travailler en boucle autonome sur ce projet sans intervention humaine.
Le pipeline est : fix → push + run manuel (Actions) → git pull → analyse → fix → re-run.
⚠ Depuis session 7, les `push` ne déclenchent plus de run — il faut lancer manuellement (Actions → Run workflow).

### Protocole de boucle autonome

```
1. Push un fix PUIS lancer un run manuel (Actions → Run workflow) — les push ne déclenchent plus de run (session 7)
2. ScheduleWakeup(270s) — cache chaud, run fini dans ce délai
3. git pull --rebase -X ours origin main
4. Lire run.log (commité par Actions) — chercher :
   - [Claude ERREUR API] → erreur API à corriger
   - [Claude raw début] → voir ce que Claude retourne réellement
   - [Gemini] → statut Gemini
5. Lire events_extracted.json → events_count
6. Critères d'arrêt : events_count >= 50 scrapés ET qualité OK
   (vrais titres, vraies dates 2026, bonnes catégories)
7. Si problème → corriger, push + run manuel, retour étape 2
```

### Accès aux logs sans gh CLI

`run.log` est commité par Actions après chaque run (ajouté à `git add` dans update.yml).
`git pull` suffit pour tout lire. Pas besoin de gh CLI ni de token API GitHub.

### Seuils de qualité

| Métrique | Minimum acceptable | Excellent |
|----------|-------------------|-----------|
| events scrapés | 50 | 200+ |
| catégories couvertes | 6/11 | 10/11 |

### Résultat de référence (20 juin 2026, sous Sonnet 4.6)
- **330 events** (29 manuels + 301 scrapés) — référentiel qualité pour valider Haiku 4.5
- Gemini non disponible (quota free tier) → scrape seul suffit
- Festival de Nîmes, Jazz à Sète, Humour (58 events), Danse OK
- ⚠ Le cinéma n'est plus extrait depuis session 7 (liens AlloCiné statiques)

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
- **AlloCiné** : JS-rendu, non scrapable → extraction films **retirée (session 7)**. La page affiche 2 liens directs vers les pages séances (Pathé `P0702`, Mégarama `W4980`).
- **Festival de Nîmes RSS** : 1 seul item — couvert par scrape JSON-LD JDS + mémoire Claude
- **Titres génériques** : RSS AgendaCulturel publie parfois "Jour 1", "Ouverture" sans titre artiste

---

## PROCHAINES ÉTAPES

- [x] Repo GitHub créé + GitHub Pages actif
- [x] Workflow Actions opérationnel (cron + run manuel ; push triggers retirés session 7)
- [x] ANTHROPIC_API_KEY configuré
- [x] GEMINI_API_KEY configuré
- [x] Architecture hybride 3 couches opérationnelle
- [x] Sections Humour + Danse dans le template
- [x] Pipeline validé : 330 events + 32 films (20 juin 2026)
- [x] Mode autonome Claude opérationnel (ScheduleWakeup + run.log)
- [x] **Redesign template2.html** — design Dark Méditerranéen, Playfair+SpaceMono, hero ★★★ (21 juin 2026)
- [x] **Optimisation coût API** (session 7) — Haiku 4.5 + cinéma supprimé + push triggers retirés → ~0,11 $/jour
- [ ] **Gemini search grounding** : cliquer "Configurer la facturation" sur clé `...Pt9Q` dans AI Studio → ~1,50€/mois → +20-50 events depuis sites JS (Festival de Nîmes officiel, Jazz à Sète, Paloma)
- [x] **AlloCiné/films** : extraction supprimée → 2 liens statiques (session 7, optimisation coût)
- [ ] Ajouter flux RSS Paloma officiel (le `/feed/` retourne blog, pas agenda)
- [ ] Évaluer `sources-enrichi.md` (92 sources) → intégrer les meilleures dans `sources.md`

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
print('events:', d['events_count'])
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
