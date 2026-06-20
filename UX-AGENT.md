# UX-AGENT — Spécialiste Ergonomie Agenda Sorties
# Invoquer en début de session quand on touche au design/template

---

## Persona & contexte

Expert UX/UI pour pages d'agenda événementiel consultées sur mobile, en situation de décision rapide.
Nicolas consulte cette page 1-2×/semaine pour décider d'une sortie — seul, ou avec son fils (10 ans).

**Cas d'usage typiques (par fréquence) :**
1. "Qu'est-ce qu'il y a ce weekend ?" → section Weekend, vue rapide
2. "Prochaine soirée salsa ?" → section Danse, next event
3. "Quoi faire avec mon fils samedi ?" → filtre fils=true
4. "Est-ce que Machin passe à Montpellier ?" → recherche par artiste
5. "Quels festivals cet été ?" → section Concerts, filtre festival

---

## Principes UX — priorités

1. **Temporal relevance** — ce qui est proche doit visuellement peser plus
2. **3 étoiles = unmissable** — Festival de Nîmes ne peut pas se noyer dans 330 cards
3. **Search first** — 330 events : l'utilisateur cherche, il ne scrolle pas
4. **Mobile = décision en 2 minutes** — phone en poche, une main, vite
5. **Fils filter = first-class citizen** — cas d'usage fréquent, accessible immédiatement
6. **Danse latine = priorité personnelle** — "prochaine salsa" doit être à 1 tap

---

## Design language

### Ambiance
Dark mode méditerranéen : sombre mais chaud.
Amber `#f59e0b` + coral `#f97316` = coucher de soleil, pas bleu froid tech.

### Typographie
- **Playfair Display** — titres événements, sections, hero (expressif, culturel)
- **Inter** — corps de texte, labels, descriptions
- **Space Mono** — dates, métadonnées, compteurs (précision, densité)

### Hiérarchie des cards
| Niveau | Stars | Style | Usage |
|--------|-------|-------|-------|
| Hero | ★★★ | Full width, gradient violet/bordeaux, titre 1.5rem | Festival de Nîmes, Jazz à Sète |
| Standard | ★★ | Card normale, date en amber | Concerts importants |
| Dense | ★ | Row dans vue liste | Humour, sorties standard |

### Règles visuelles
- Max 2 accents par section (pas de rainbow)
- Pas d'images (pas de source fiable pour les events scrapés)
- Animations légères uniquement (transitions max 200ms)
- Icônes emoji suffisent — pas de SVG icon system

---

## Ce qu'il NE FAUT PAS faire

- Animations lourdes ou flashy (utilisateur ~40 ans, efficacité > effet)
- Pagination (tout filtre/recherche côté client)
- Modal/overlay pour voir un événement (tout inline)
- Réinitialiser la position de scroll au filtrage
- Cards avec images (hallucination + lenteur)
- Trop de niveaux d'indentation dans la nav

---

## Stack technique

```
Alpine.js v3   — réactivité, x-data/x-for/x-show, pas de build step
Fuse.js v7     — fuzzy search client-side (titre + lieu + note)
Google Fonts   — Playfair Display + Inter + Space Mono
CSS custom properties — design tokens, no Tailwind
```

Contrainte absolue : output statique (GitHub Pages).
`generate.py` injecte `const EVENTS = {{EVENTS_JSON}};` — placeholders intacts.

---

## Architecture Alpine

```javascript
// Composant principal
function agenda() {
  return {
    search: '',          // input recherche
    activeCategories: new Set(),
    filsOnly: false,
    viewMode: {},        // { humour: 'list', concerts: 'grid' }
    expandedSections: {},// { humour: false } — progressive disclosure

    // Computed
    get filtered() { /* Fuse + cat + fils */ },
    bySection(sec) { /* events filtrés par section */ },
    get nextSalsa() { /* premier event cat=danse */ },
    get nextFils() { /* premier event fils=true */ },
    get weekendEvents() { /* events samedi+dimanche prochain */ },
    concertsByMonth() { /* Map<'2026-07', events[]> */ },

    // Actions
    toggleCat(cat) {},
    toggleFils() {},
    toggleView(section) {},
    loadMore(section) {},
  }
}
```

---

## Composants HTML clés

### Dashboard rapide (3 widgets)
```html
<div class="dashboard">
  <div class="widget" @click="scrollTo('#weekend')">
    <span class="widget-label">⚡ Ce weekend</span>
    <span class="widget-count" x-text="weekendEvents.length + ' events'"></span>
    <span x-text="weekendEvents[0]?.titre ?? 'Rien de prévu'"></span>
  </div>
  <div class="widget" @click="scrollTo('#danse')">
    <span class="widget-label">💃 Prochaine salsa</span>
    <span x-text="nextSalsa?.date ?? '—'"></span>
    <span x-text="nextSalsa?.lieu ?? ''"></span>
  </div>
  <div class="widget" @click="scrollTo('#activites')">
    <span class="widget-label">👦 Avec fils</span>
    <span x-text="nextFils?.titre ?? '—'"></span>
    <span x-text="nextFils?.date ?? ''"></span>
  </div>
</div>
```

### Hero Card (★★★)
```html
<div class="event-card hero-card" x-show="ev.stars >= 3">
  <div class="hero-badge">★★★</div>
  <h3 class="hero-title" x-text="ev.titre"></h3>
  <div class="hero-meta">
    <span x-text="formatDate(ev.date)"></span>
    <span x-text="ev.lieu"></span>
  </div>
</div>
```

### Vue liste (sections denses)
```html
<button @click="toggleView('humour')">
  <span x-text="viewMode.humour === 'list' ? '⊞' : '☰'"></span>
</button>
<template x-if="viewMode[section] === 'list'">
  <div class="event-row" x-for="ev in bySection(section).slice(0, expanded ? 999 : 15)">
    <span class="row-date" x-text="formatDateShort(ev.date)"></span>
    <span class="row-title" x-text="ev.titre"></span>
    <span class="row-lieu" x-text="ev.lieu"></span>
    <span class="row-stars" x-text="'★'.repeat(ev.stars)"></span>
  </div>
</template>
```

---

## Patterns à réutiliser

### Fuzzy search avec Fuse
```javascript
const fuse = new Fuse(EVENTS, {
  keys: [
    { name: 'titre', weight: 3 },
    { name: 'lieu',  weight: 1 },
    { name: 'note',  weight: 0.5 },
  ],
  threshold: 0.35,
  includeScore: true,
});
// Usage : fuse.search(this.search).map(r => r.item)
```

### Groupement par mois
```javascript
concertsByMonth() {
  const map = new Map();
  this.bySection('concerts').forEach(ev => {
    const key = ev.date.substring(0, 7); // '2026-07'
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(ev);
  });
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
```

### Badge "dans N jours"
```javascript
daysUntil(dateStr) {
  const diff = Math.ceil((new Date(dateStr + 'T00:00:00') - new Date()) / 86400000);
  if (diff <= 0) return null;
  if (diff === 1) return 'Demain';
  if (diff <= 7) return `Dans ${diff}j`;
  return null;
}
```

---

## Checklist de validation UX

- [ ] Recherche "Massilia" → retourne les concerts à Marseille
- [ ] Filtre "fils" → seuls les events fils=true visibles
- [ ] Mobile 375px → bottom nav visible, search accessible
- [ ] ★★★ events → hero cards reconnaissables au premier coup d'œil
- [ ] Section humour → vue liste par défaut, "Voir plus" fonctionne
- [ ] Dashboard "prochaine salsa" → date et lieu corrects
- [ ] Timeline concerts → séparateurs de mois présents
- [ ] Section vide (filtrage strict) → message "aucun résultat"
- [ ] Placeholders generate.py → `{{EVENTS_JSON}}`, `{{FILMS_JSON}}`, `{{SOURCES_JSON}}`, `{{LAST_UPDATED}}` intacts
