# CLAUDE.md

Ce fichier guide Claude Code (claude.ai/code) lorsqu'il travaille dans ce dépôt.

## Nature du projet

**ProIndemni** — outil d'aide à la rédaction de courriers de sinistre d'assurance professionnelle,
destiné aux TPE/PME, artisans et commerçants français.

Application **statique** : pas de framework, pas de build, pas de `package.json`. Le code
applicatif (HTML + CSS + JavaScript vanilla) tient dans un seul fichier `index.html`, accompagné
d'**une seule dépendance locale** : `pdf-lib.min.js` (build UMD v1.17.1 de pdf-lib, ~500 Ko),
chargée via `<script src="pdf-lib.min.js">` juste avant le script principal et exposant la
globale `window.PDFLib`. Elle sert à générer de **vrais PDF** (fusion des pages des PDF joints),
impossible nativement dans le navigateur. Le fichier doit être présent à côté de `index.html`.
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
sed -n '886,2179p' index.html | node --check
```

## Architecture

Le fichier suit une structure en deux blocs : le `<style>` (design tokens + composants),
puis le `<body>` (sections HTML), puis un unique `<script>` final (logique applicative).

Sections de la page, dans l'ordre :
1. **Hero** — lettre d'exemple (pur décor, `aria-hidden`)
2. **Étapes** — les 6 gestes du parcours
3. **Votre dossier** (`#dossier`) — regroupe trois sous-sections numérotées dans une même section :
   - `.dossier-sub#documents` « Étape 1 · Les justificatifs » — checklist par type de sinistre
   - `.dossier-sub#contrat` « Étape 2 · Votre contrat » — saisie des clauses (franchise, plafond…)
   - `.dossier-sub#delais` « Étape 3 · Vos échéances » — calculateur de dates limites
   - plus un bloc **Sauvegarde / restauration** (`.data-io`, boutons `#btnExport` / `#btnImport`)
4. **Comprendre votre indemnisation** (`#comprendre`, section `section--dark comprendre`) — pédagogie
   « la réalité du terrain » : une frise `.jny` en 6 étapes (le parcours réel d'un sinistre) + une
   grille `.comprendre-grid` de 4 cartes (perte d'exploitation / préparer l'expert / anticiper
   l'après / refus et réductions fréquents) + un encart `.comprendre-takeaway` avec CTA vers
   `#rediger`. Contenu issu de la recherche terrain (cf. mémoire), ton « ni minimiser ni promettre ».
   La carte 04 porte un lien `.go` avec `data-letter-link="contestation"` qui pré-sélectionne le
   courrier « Contester un refus » via `setLetter()` (défini à côté de `syncLetterButtons()`).
5. **Générateur** (`#rediger`) — le courrier (déclaration / relance / mise en demeure / médiateur / contestation d'un refus)
6. **Partenaires** + **pied de page** (mentions légales)

Les ancres `#documents` / `#contrat` / `#delais` sont conservées sur les `.dossier-sub` (les liens
du menu restent valables).

### Données clés (dans le `<script>`)

- `CATEGORIES` — objet clé → `{ label, icon }` : les emplacements de dépôt côté assureur
  (`declaration`, `contrat`, `photos`, `factures`, `devis`, `comptabilite`, `rapports`,
  `correspondance`).
- `CHECKLISTS` — objet clé → `{ title, hint, docs[] }`. Chaque `doc` est
  `{ category, label, where, template }` (`category` = emplacement de dépôt chez l'assureur,
  `where` = « Où le trouver », affiché en surbrillance à l'écran mais **exclu du PDF** ;
  `template` = texte pré-rempli dans la zone de note).
- `state = { letterType }` — `"declaration" | "relance" | "demeure" | "mediateur" | "contestation"`.
- `contract` — les clauses lues depuis le formulaire « Mon contrat ».
- `postes` — tableau `[{ id, label, montant }]` du chiffrage du préjudice (ligne par ligne),
  rendu par `renderPostes()`/`renderPostesTotal()`, total par `prejudiceTotal()`. Remplace l'ancien
  champ libre `fMontant`.
- `buildLetter()` — construit le courrier, retourne `{ subject, pj, meta, sender, recipient, body, sign }`.
  La ligne `pj` est dynamique via `pjLine(fallback)` (pièces cochées + noms des fichiers joints) ;
  le montant du préjudice est injecté depuis `prejudiceTotal()` avec détail des postes quand `> 1`.
- `generateDossierPdf(scope)` — (async, pdf-lib) génère un **vrai PDF téléchargeable** :
  bordereau (documents groupés par catégorie + détail des cochés), photos en pages, et les pages
  des PDF joints **entièrement fusionnées** (`copyPages`, pas d'`embed`). `scope` = clé de catégorie
  (`declaration`, `contrat`, …) ou `"all"` pour le dossier complet. En `"all"`, le courrier est ajouté
  via `drawLetterPdf()` **uniquement si** la case `#chkIncludeLetter` (« Inclure le courrier dans le
  dossier complet », cochée par défaut) est active — testé par `includeLetter()`. Boutons par rubrique
  rendus par `renderRubriques()`, bouton « Dossier complet » câblé dans `setupChecklist()`. Chaque
  photo est placée sur sa propre page avec une légende (`label + nom de fichier`), et chaque page de
  PDF joint reçoit un **pied de page** (barre blanche + `label + nom de fichier` + `page n/N`) pour
  identifier la feuille. Helpers : `dataUrlToBytes()`, `pdfText()` (retour à la ligne + saut de page),
  `wrapPdfText()`, `pdfSafe()` (filtre les caractères hors WinAnsi), `downloadPdf()`.
- `generateLetterPdf()` — (async, pdf-lib) génère le **courrier prêt à envoyer** en PDF (en-tête LRAR,
  expéditeur à gauche, destinataire/méta à droite, objet en gras, corps, signature), câblé sur le
  bouton `#btnPdf` dans `setupActions()`. La mise en forme est mutualisée dans `drawLetterPdf()`
  (réutilisée par le dossier complet).
- Le document de catégorie `declaration` n'a **pas de zone de note** : son panneau affiche à la place
  un lien `#rediger` (« Rédiger la déclaration dans « Votre courrier » »), car la déclaration EST le
  courrier.
- `deadlineType` — `"standard" | "vol"` (le vol raccourcit le délai de déclaration à 2 jours).
- `renderDeadlines()` — échéancier automatique : les dates de relance / mise en demeure / saisine
  du Médiateur sont calculées **à partir du dernier jour pour déclarer** (`decl`), plus une ligne
  récapitulative `.calc-summary`. La prescription de 2 ans court depuis la date du sinistre.

### Sauvegarde locale

Clé `localStorage` : `indemnipro-state-v1` (`STORAGE_KEY`). `saveState()`/`loadState()`
persistent les champs du générateur, du contrat, la date du sinistre, le type de courrier,
le type de sinistre actif, les cases cochées, les notes, les postes de préjudice et les pièces
jointes par document (nom/taille/type uniquement — le contenu des images `dataUrl` n'est **pas**
persisté, il est lu en mémoire à la session). Les pièces jointes sont rattachées à chaque document
(`docFiles`), pas à un bloc global.

En complément, `setupDataIO()` câble un **export/import JSON** complet du dossier (`#btnExport`
télécharge `proindemni-dossier-*.json`, `#btnImport` réimporte via `#importFile` + `applyState`).
Aucune donnée ne transite par un serveur.

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
`index.html`, `pdf-lib.min.js`, `icon.png` et `og-image.png` sont à la racine. **Configuration requise une fois**
(à faire à la main dans l'UI GitHub) : Settings → Pages → Source « Deploy from a branch »,
branch `main`, dossier `/ (root)`. Sans cette source, aucun déploiement n'a lieu et l'URL
renvoie 404 malgré un `has_pages: true`. Les URLs de partage (Open Graph) pointent vers
ce domaine — à mettre à jour si le déploiement change.
