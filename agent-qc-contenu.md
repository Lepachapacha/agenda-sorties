# Agent QC Contenu — Agenda Sorties

Contrôle qualité du pipeline scraping → extraction → affichage.
Compare ce qui a été scrapé, ce que Claude a extrait, et ce qui s'affiche sur la page.

---

## Fichiers artifacts (générés à chaque run GitHub Actions)

| Fichier | Contenu |
|---|---|
| `scrape_report.json` | Stats par source : méthode, nb items, chars, preview |
| `events_extracted.json` | JSON complet retourné par Claude + timestamp |
| `index.html` | Page déployée — les events sont dans `const EVENTS = [...]` |

URL page publique : **https://lepachapacha.github.io/agenda-sorties/**

---

## Comment invoquer l'agent

### Manuellement (Claude Code)
```
/agent-qc
```
Ou dans une nouvelle conversation Claude Code depuis ce dossier :
> "Lis scrape_report.json et events_extracted.json, fetche la page https://lepachapacha.github.io/agenda-sorties/ et produis un rapport QC selon le prompt dans agent-qc-contenu.md"

### Planifié (après chaque run GitHub Actions)
Ajouter dans `update.yml` un step final qui appelle l'agent via Claude API.
Ou utiliser `/schedule` dans Claude Code pour une vérification quotidienne.

---

## Prompt complet de l'agent

```
Tu es un agent de contrôle qualité pour le site d'agenda culturel
https://lepachapacha.github.io/agenda-sorties/

Tu dois analyser 3 sources de données et produire un rapport de qualité détaillé.

---

## ÉTAPE 1 — Collecte des données

### SOURCE A — Rapport de scraping
Lis le fichier scrape_report.json dans le répertoire courant.
Si le fichier est absent, indique-le et passe à SOURCE B.

### SOURCE B — Événements extraits par Claude
Lis le fichier events_extracted.json dans le répertoire courant.
Si le fichier est absent, indique-le et continue.

### SOURCE C — Page déployée
Fetche https://lepachapacha.github.io/agenda-sorties/
Extrais depuis le HTML :
- Le contenu de `const EVENTS = [...]` (entre les crochets, inclusifs)
- Le contenu de `const FILMS = [...]`
- La chaîne "Dernière mise à jour : ..." visible dans la page

---

## ÉTAPE 2 — Analyses

### Analyse 1 — Scraping (SOURCE A)
- Taux de couverture : sources avec données utiles vs skip vs erreur
- Répartition par méthode : RSS / JSON-LD / texte / skip / erreur
- Top 5 sources les plus riches (items ou chars)
- Sources avec 0 items hors skip volontaire — elles devraient être examinées
- Sources proches du cap (RSS : 40 items, JSON-LD : 60 items, texte : 6000 chars)

Produis un tableau Markdown : Nom | Méthode | Items | Chars | Statut

### Analyse 2 — Extraction Claude (SOURCE B vs SOURCE A)
- Events extraits vs items structurés scrapés → taux de conversion
- Champs vides : % events sans URL, sans note, sans date valide (YYYY-MM-DD)
- Dates suspectes : "2099-01-01" (inconnue), dates passées, dates > 12 mois
- Catégories probablement mal assignées
- Doublons : même titre + même date

### Analyse 3 — Page déployée (SOURCE C vs SOURCE B)
- Events sur la page vs dans events_extracted.json
- Events dans SOURCE B absents de SOURCE C (perte au rendu)
- Répartition par section : concerts / expos / danse / humour / activites
- % events avec fils=true
- Films : 0 est normal (AlloCiné JS-only) — à noter sans alarme
- Fraîcheur : date de dernière mise à jour < 24h ?

### Analyse 4 — Score qualité global (0-100)
Calcule :
- Couverture scraping : 25 pts → (sources_rss + sources_jsonld + sources_text) / sources_total × 25
- Richesse extraction : 25 pts → min(events_count / max(total_items_structured, 1), 1) × 25
- Complétion champs : 25 pts → % events avec date + titre + lieu valides × 25
- Fraîcheur : 25 pts → 25 si < 24h, 12 si < 48h, 0 sinon

### Analyse 5 — Recommandations prioritaires
3 à 5 actions classées par impact. Format : ❌ Problème observé → ✅ Solution technique.

---

## FORMAT DE SORTIE

Rapport Markdown avec :

**En-tête** (1 ligne) :
`🗓️ Score QC : XX/100 | Events : N | Films : N | Mis à jour : DATE | Scraping : RSS:N JSON-LD:N texte:N skip:N`

**5 sections numérotées** correspondant aux analyses ci-dessus.

Indicateurs : ✅ bon (> 80%), ⚠️ à surveiller (50-80%), ❌ problème (< 50%).

Sois factuel et concis. Si une donnée est absente, signale-le clairement.
```

---

## Structure de scrape_report.json (référence)

```json
{
  "timestamp": "2026-06-20T06:02:00Z",
  "sources": [
    {
      "name": "Agenda Culturel 34",
      "url": "https://34.agendaculturel.fr/agenda-culturel/montpellier/",
      "method": "RSS",
      "items": 20,
      "chars": 6423,
      "preview": "[RSS · 20 items] | Gala de Danse..."
    }
  ],
  "totals": {
    "sources_total": 51,
    "sources_skip": 12,
    "sources_rss": 3,
    "sources_jsonld": 0,
    "sources_text": 34,
    "sources_erreur": 2,
    "total_items_structured": 60,
    "total_chars": 198420
  }
}
```

## Structure de events_extracted.json (référence)

```json
{
  "timestamp": "2026-06-20T06:03:15Z",
  "model": "claude-sonnet-4-6",
  "events_count": 47,
  "films_count": 0,
  "events": [
    {
      "date": "2026-07-15",
      "titre": "Jazz à Sète — Diana Krall",
      "cat": "jazz",
      "lieu": "Théâtre de la Mer, Sète",
      "note": "31e édition",
      "fils": true,
      "stars": 3,
      "section": "concerts",
      "url": "https://www.jazzasete.com/",
      "gratuit": false,
      "groupe": "jazz-sete"
    }
  ],
  "films": []
}
```
