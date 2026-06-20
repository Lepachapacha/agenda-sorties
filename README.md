# Agenda Sorties — Montpellier · Nîmes · Sète · Béziers · Marseille

Page personnelle de sorties culturelles — concerts, festivals, cinéma, danse latine, humour.
Mise à jour automatique quotidienne via GitHub Actions.

**URL publique :** https://lepachapacha.github.io/agenda-sorties
**Compte GitHub :** Lepachapacha

## Ajouter un événement

Éditer uniquement `agenda-config.md` (source de vérité, priorité absolue) :

```
- DATE | TITRE | CATEGORIE | LIEU | NOTE | AVEC_FILS(oui/non) | ETOILES(1-3) | URL | GROUPE
```

Catégories : `festival` `concert` `theatre` `expo` `danse` `jazz` `classique` `electro` `feria` `humour` `activite`

## Stack

- **Scraping :** Python — RSS → JSON-LD → texte brut (47 sources)
- **Enrichissement :** Gemini 1.5 Flash (Google Search grounding — facturation requise)
- **Extraction :** Claude Sonnet 4.6 (streaming, max_tokens=32768)
- **Frontend :** HTML/CSS/JS vanilla · Alpine.js · Fuse.js · GitHub Pages
- **CI/CD :** GitHub Actions (cron 6h UTC + push triggers)

## Design

Template actif : `template2.html` — design « Terrasse » (Syne + Inter, fond `#F7F8F4`, cartes date-block).
Template backup : `template.html` — dark theme (Playfair Display, fond `#08080c`).
