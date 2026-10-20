# CLAUDE.md

Ce fichier guide Claude Code (claude.ai/code) lorsqu'il travaille dans ce dépôt.

## Nature du projet

**IndemniPro** — outil d'aide à la rédaction de courriers de sinistre d'assurance professionnelle,
destiné aux TPE/PME, artisans et commerçants français.

Application **statique en un seul fichier `index.html`** : pas de framework, pas de build,
pas de `package.json`, pas de dépendances. HTML + CSS + JavaScript vanilla dans le même fichier.
Aucune donnée n'est envoyée sur un serveur — tout est stocké dans le `localStorage` du navigateur.

## Prévisualiser / tester

Ouvrir `index.html` directement dans un navigateur, ou lancer un serveur local :

```bash
python -m http.server 5173
# puis http://localhost:5173
```

Pas de suite de tests — vérification manuelle dans le navigateur. Le JavaScript peut être
contrôlé en syntaxe via :

```bash
sed -n '791,1621p' index.html | node --check
```

## Architecture

Le fichier suit une structure en deux blocs : le `<style>` (design tokens + composants),
puis le `<body>` (sections HTML), puis un unique `<script>` final (logique applicative).

Sections de la page, dans l'ordre :
1. **Hero** — lettre d'exemple (pur décor, `aria-hidden`)
2. **Étapes** — les 6 gestes du parcours
3. **Checklist documents** (`#documents`) — liste des justificatifs par type de sinistre + pièces jointes
4. **Délais** (`#delais`) — calculateur de dates limites
5. **Mon contrat** (`#contrat`) — saisie des clauses (franchise, plafond…)
6. **Générateur** (`#rediger`) — le courrier (relance / mise en demeure / médiateur)
7. **Partenaires** + **pied de page** (mentions légales)

### Données clés (dans le `<script>`)

- `CHECKLISTS` — objet clé → `{ title, hint, docs[] }`. Chaque `doc` est `{ label, where }`
  (`where` = indication « Où le trouver », affichée en petit sous le libellé).
- `state = { letterType }` — `"relance" | "demeure" | "mediateur"`.
- `contract` — les clauses lues depuis le formulaire « Mon contrat ».
- `buildLetter()` — construit le courrier, retourne `{ subject, pj, meta, sender, recipient, body, sign }`.
- `printDossier()` — génère un dossier complet (courrier + bordereau + photos) dans une
  fenêtre `window.open` puis déclenche l'impression.
- `deadlineType` — `"standard" | "vol"` (le vol raccourcit le délai de déclaration à 2 jours).

### Sauvegarde locale

Clé `localStorage` : `indemnipro-state-v1` (`STORAGE_KEY`). `saveState()`/`loadState()`
persistent les champs du générateur, du contrat, la date du sinistre, le type de courrier,
le type de sinistre actif, les cases cochées et les pièces jointes (nom/taille/type uniquement —
le contenu des images `dataUrl` n'est **pas** persisté, il est lu en mémoire à la session).

## Règles de fond (délais, droit)

- Délai de déclaration : **5 jours ouvrés** (2 jours pour un vol) — art. L. 113-2 du Code des assurances.
- Indemnisation sous 30 jours après accord (art. L. 113-5) ; à défaut, intérêts au double du taux légal.
- Prescription : 2 ans (art. L. 114-1).
- Saisine du Médiateur possible après réclamation écrite restée plus de 2 mois sans issue.

Les mentions légales insistent sur le caractère indicatif (pas de conseil juridique, pas
d'intermédiaire en assurance, non immatriculé ORIAS).

## Design

- Pas de framework CSS — variables dans `:root` (`--navy`, `--red`, `--paper`, `--ink`…).
  Palette « papier / timbre » : encre navy `#1E3A8A`, timbre rouge `#C8102E`, papier `#F6F4EF`.
- Polices Google Fonts : Fraunces (titres), Work Sans (corps), IBM Plex Mono (labels).
- L'impression n'imprime que la lettre (`@media print` cible `#letterSheet`).

## Déploiement

GitHub Pages — repo `DCY92130/indemnipro`, servi à `https://dcgy92130.github.io/indemnipro/`.
`index.html`, `icon.png` et `og-image.png` sont à la racine ; le push sur `main` suffit
(site déployé depuis la racine de `main`). Les URLs de partage (Open Graph) pointent vers
ce domaine — à mettre à jour si le déploiement change.
