# Conception — Module payant « Audit de contrat » (ProIndemni)

> Statut : **conception** — rien n'est activé. Le paywall, la drop zone et
> l'orientation sont spécifiés mais non câblés.
> Version : v0.1 (2026-11-04)

## 1. Objectif

Permettre à un commerçant, une association ou une TPE de **déposer son contrat
d'assurance** (PDF) via une zone de dépôt, d'en obtenir un **relevé factuel et
neutre** des clauses et montants d'indemnisation, puis d'être **orienté** vers
le dossier (checklist) et le courrier (générateur) qui correspondent à sa
situation — le tout sans jamais exposer ses données personnelles.

Trois principes non négociables :

1. **Neutralité** — le module *décrit* le contrat, il ne le *juge* pas.
   Pas de « points de vigilance », pas de « niveau de couverture », pas d'avis.
2. **Minimisation des données** — le contrat est pseudonymisé *avant* tout
   envoi à un modèle externe, et **jamais stocké** après traitement.
3. **Aiguillage** — le résultat aboutit à un CTA qui pré-remplit le dossier /
   le courrier existant (réutilise `setLetter()` / `selectType()`).

## 2. État des lieux — ce qui existe déjà

Le dossier `backend/` contient déjà le pipeline suivant (fonctionnel) :

```
PDF ─► PdfExtractor (PyMuPDF, marqueurs « --- Page N --- »)
    ─► Anonymizer (regex : email / tel / SIRET / SIREN / IBAN / adresse / nom)
    ─► DeepSeekClient (SDK openai, response_format=json_object)
    ─► AuditResult (validation Pydantic, relance si JSON invalide)
```

**Ce qui manque** pour répondre au besoin :

| Besoin | État |
|---|---|
| Extraction du texte PDF | ✅ `pdf.py` |
| Endpoint d'upload | ✅ `/audit` (multipart PDF) |
| Anonymisation | ⚠️ regex uniquement, lacunes connues (noms en prose) |
| Extraction des clauses/montants | ⚠️ prompt actuel **non neutre** (`points_de_vigilance`, `resume`) |
| **Drop zone front** | ❌ inexistante |
| **Orientation vers dossier/courrier** | ❌ inexistante |
| **Paywall** | ❌ inexistant |

## 3. Architecture cible

```
[Front — index.html : nouvelle section « Audit de contrat »]
    ├── Drop zone (drag & drop + <input type="file" accept=".pdf">)
    │      ├── validation client : type PDF, taille ≤ 25 Mo, ≤ 60 pages
    │      └── gate payant (désactivé, cf. §6) → bouton « Lancer l'audit »
    │
    └── POST /audit  ─────────────────────────────────────────────► backend FastAPI
           │
           ├── 1. PdfExtractor            (existant)
           ├── 2. PresidioAnonymizer      (NOUVEAU — remplace la regex, cf. §4)
           ├── 3. NeutralExtractor (LLM)  (NOUVEAU — prompt neutre, cf. §5)
           ├── 4. OrientationService      (NOUVEAU — déterministe, sans LLM, cf. §6)
           └── 5. Suppression du PDF temporaire (déjà en place)
```

La réponse JSON devient :

```jsonc
{
  "audit": { /* relevé factuel, cf. §5 */ },
  "orientation": { /* cf. §6 */
    "courrier": "contestation",       // une des 5 valeurs de state.letterType
    "checklist": "emeute-pillage",    // une clé de CHECKLISTS (ou null)
    "raisons": ["La garantie perte d'exploitation est absente (Page 14)"]
  }
}
```

## 4. Anonymisation — la réponse à « quelque chose d'existant et gratuit »

### Recommandation : **Microsoft Presidio** (open-source, MIT, self-hosted)

C'est *le* framework de référence pour la détection + l'anonymisation de données
personnelles (ex `microsoft/presidio`, désormais `data-privacy-stack/presidio`).
Gratuit, auto-hébergé, production-ready.

- **Analyzer** : détecte les entités (PERSON, LOCATION, EMAIL, PHONE_NUMBER,
  IBAN_CODE…) via spaCy NER **+** expressions régulières **+** `PatternRecognizer`
  personnalisés.
- **Anonymizer** : remplace par des pseudonymes/tokens (ou chiffre, ou masque).
- **Français** : modèle spaCy `fr_core_news_lg` (ou `xx_ent_wiki_sm` multilingue)
  **+** on **réutilise les regex françaises existantes** (SIRET/SIREN/IBAN/
  téléphone/adresse dans `anonymizer.py`) comme `PatternRecognizer` custom —
  c'est exactement le point d'extension prévu par Presidio (pluggable).

**Pourquoi PAS un « site gratuit » :** un contrat d'assurance contient des
données personnelles et financières (nom, SIRET, activité, montants assurés).
L'envoyer à un service web tiers est une **violation RGPD** et un risque
commercial majeur. La règle : traitement **local / sur ton serveur**, jamais sur
le site d'un tiers. Presidio satisfait cette règle car il s'exécute chez toi.

### Honnêteté sur la limite

Presidio fait de la **pseudonymisation**, pas une anonymisation absolue : les
noms d'entreprise disséminés dans la prose (« la Société s'engage… ») restent
un cas limite, même avec NER. Deux lignes de défense recommandées :

1. **Presidio** (déterministe, auditable) en première passe.
2. **Passe LLM de relecture/rédaction** (optionnelle, cf. prompt §8.2) qui ne
   voit qu'un texte *déjà* masqué et ne cherche que les résidus.

Et surtout : pour un produit payant destiné à la France, remplacer **DeepSeek
(hors UE)** par un modèle hébergé en UE (Mistral/Llama) — le code est déjà prêt,
il suffit de changer `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`.

## 5. Extraction neutre (le cœur)

Reprendre le schéma existant (`schemas.py`) mais **retirer** les champs d'avis
(`points_de_vigilance`, `resume`) et **ajouter** les champs factuels qui
manquent. Le prompt associé est au §8.1.

Schéma cible (sortie du LLM) :

```
synthese            → type_contrat, assureur, activite_declaree, periode_validite…
garanties[]         → nom, couverte, franchise, plafond, capital_indemnite, exclusions, source
franchises_globales → franchise générale applicable (ou « Non mentionné »)
exclusions_generales[]
perte_exploitation  → couverte, franchise, delai_carence, duree_max, indemnite_journaliere
obligations_delais  → delai_declaration_sinistre, prescription…
montants_cles[]     → [{ intitule, montant, source }]  ← tout chiffre clé, neutre
```

Règles de fond conservées : **aucune supposition** (« Non mentionné dans le
document » sinon), **citation de la page** pour chaque info, montants reproduits
**tels qu'écrits avec leur unité**, garanties absentes listées explicitement.

## 6. Orientation vers dossier / courrier (déterministe)

L'aiguillage ne passe **pas** par le LLM (risque d'avis + d'hallucination) : il
est réalisé par des **règles** sur les champs extraits. Table de règles initiale :

| Condition (sur l'audit) | → courrier | → checklist | Raison factuelle |
|---|---|---|---|
| `perte_exploitation.couverte ∈ {Non, Non mentionné}` | `contestation` | — | perte d'exploitation non garantie |
| exclusion contient « émeute / attroupement / mouvement populaire » | `contestation` | `emeute-pillage` | garantie émeutes exclue / restreinte |
| `obligations_delais.delai_declaration` < 5 j OU sinistre = vol | `declaration` | — | délai de déclaration raccourci |
| garantie vol `couverte = Non` | `contestation` | — | vol non couvert |
| rien d'anormal détecté | `declaration` | — | aiguillage par défaut |

Chaque résultat est exprimé **uniquement par des faits** (« la garantie X est
absente (Page 14) »), jamais par un jugement. Le front transforme ce résultat en
CTA qui appelle `setLetter(courrier)` et/ou `selectType(checklist)` — les mêmes
fonctions déjà utilisées par l'aiguillage existant.

## 7. Paywall (désactivé pour l'instant)

- **Feature flag** `AUDIT_ENABLED=false` : tant qu'il est à `false`, la section
  affiche « Bientôt disponible » à la place de la drop zone active.
- **Option la plus simple à terme** : **Stripe Payment Link** (aucun backend de
  facturation à écrire) → après paiement, URL de retour avec session signée →
  débloque N audits. Alternative : Stripe Checkout + webhook.
- **Quota** : N audits d'essai gratuits, puis gate. À câbler côté backend
  (middleware) **après** activation du paiement, pas avant.

## 8. Prompts (générés via le skill meta-prompt)

### 8.1 — Extraction neutre des clauses et montants (système)

```
## Rôle
Tu es un lecteur-greffier de contrats d'assurance multirisque professionnels
(TPE/PME, artisans, commerçants français). Tu ne conseilles pas : tu produis un
relevé factuel, exhaustif et fidèle de ce que dit le document.

## Contexte
On te fournit le texte brut d'un contrat d'assurance, extrait d'un PDF. Chaque
page est précédée du marqueur « --- Page N --- ». Les données personnelles ont
déjà été remplacées par des jetons entre crochets ([NOM_MASQUE], [SIRET_MASQUE]…).
Ce relevé alimente un outil d'aide à la rédaction de courriers de sinistre ;
il doit rester strictement neutre.

## Tâche
Lis l'intégralité du document et produis un relevé structuré :
1. Identifie le contrat (type, assureur, activité déclarée, période de validité).
2. Liste TOUTES les garanties, en relevant pour chacune : franchise, plafond,
   capital d'indemnité, exclusions propres.
3. Relève les exclusions générales, la franchise globale éventuelle, et les
   modalités de la perte d'exploitation si présentes.
4. Relève les délais et obligations (déclaration de sinistre, prescription).
5. Recense tout montant chiffré clé (capital, franchise, indemnité journalière…)
   avec sa source.

## Contraintes
- Fonde-toi exclusivement sur le texte fourni ; si une information n'y figure
  pas explicitement, écris exactement « Non mentionné dans le document » — cela
  évite toute invention.
- Cite la page (ou la clause) de chaque information dans le champ « source » —
  cela permet à l'utilisateur de vérifier.
- Reproduis chaque montant tel qu'il est écrit, avec son unité — cela garantit
  la fidélité.
- Reste factuel : décris ce que dit le contrat sans qualifier (pas de « élevé »,
  « insuffisant », « à surveiller ») — la sortie doit être un miroir, pas un avis.
- Liste aussi les garanties absentes en indiquant « Non » plutôt que de les
  omettre — cela reflète la couverture réelle.
- Réponds UNIQUEMENT en JSON valide conforme au schéma, sans texte ni markdown
  autour — cela permet une intégration machine fiable.

## Format de sortie
{
  "synthese": {
    "type_contrat": "…", "assure": "…", "assureur": "…",
    "numero_contrat": "…", "activite_declaree": "…",
    "periode_validite": "…", "date_effet": "…"
  },
  "garanties": [
    {
      "nom": "…", "couverte": "Oui | Partielle | Non | Non mentionné dans le document",
      "franchise": "…", "plafond": "…", "capital_indemnite": "…",
      "exclusions": "…", "source": "Page N"
    }
  ],
  "franchises_globales": "…",
  "exclusions_generales": ["…"],
  "perte_exploitation": {
    "couverte": "…", "franchise": "…", "delai_carence": "…",
    "duree_max_indemnisation": "…", "indemnite_journaliere": "…", "source": "…"
  },
  "obligations_delais": {
    "delai_declaration_sinistre": "…", "modalites_declaration": "…",
    "prescription": "…", "autres": "…"
  },
  "montants_cles": [ { "intitule": "…", "montant": "…", "source": "Page N" } ]
}

## Exemples
<example>
"garanties": [
  { "nom": "Incendie et risques annexes", "couverte": "Oui",
    "franchise": "500 €", "plafond": "300 000 €",
    "capital_indemnite": "300 000 €", "exclusions": "Non mentionné dans le document",
    "source": "Page 4" },
  { "nom": "Perte d'exploitation", "couverte": "Non",
    "franchise": "Non mentionné dans le document",
    "plafond": "Non mentionné dans le document",
    "capital_indemnite": "Non mentionné dans le document",
    "exclusions": "Non mentionné dans le document", "source": "Page 6" }
]
</example>

## Placeholders
- {{TEXTE_CONTRAT_ANONYMISE}} — le texte du contrat déjà pseudonymisé, injecté
  comme message « user » à la suite de ce prompt système.
```

### 8.2 — Passe de relecture / rédaction des résidus (optionnelle)

À n'utiliser qu'**après** Presidio, et uniquement sur un texte déjà masqué.

```
## Rôle
Tu es un relecteur spécialisé en protection des données. Tu repères les données
personnelles résiduelles dans un texte déjà partiellement pseudonymisé.

## Contexte
Le texte ci-dessous a déjà subi un premier masquage (jetons entre crochets).
Certaines données personnelles ont pu échapper au masquage, notamment les noms
de personnes ou d'entreprises disséminés dans la prose.

## Tâche
Réécris l'intégralité du texte en remplaçant toute donnée personnelle résiduelle
par un jeton neutre [TYPE_MASQUE]. Ne renvoie QUE le texte réécrit, sans
explication ni liste des valeurs d'origine.

## Contraintes
- Ne masque QUE les données personnelles : noms de personnes physiques ou morales,
  adresses, téléphones, emails, numéros SIRET/SIREN/IBAN, immatriculations — afin
  de ne pas dégrader l'extraction des clauses.
- Préserve intégralement les montants d'assurance (franchises, plafonds,
  capitaux) et les termes techniques du contrat (garanties, exclusions) — ce ne
  sont pas des données personnelles.
- Ne révèle jamais la valeur d'origine : remplace, ne recopie pas à côté — afin
  de garantir la confidentialité.
- Conserve la structure et les marqueurs « --- Page N --- » à l'identique.

## Format de sortie
Le texte intégral, réécrit, en texte brut uniquement.

## Placeholders
- {{TEXTE_PREMIER_MASQUAGE}} — la sortie de la passe Presidio, injectée en
  message « user ».
```

## 9. Plan d'implémentation (ordre conseillé)

1. **Backend — anonymisation** : brancher Presidio (`presidio-analyzer`,
   `presidio-anonymizer`, modèle `fr_core_news_lg`) + réutiliser les regex
   existantes comme `PatternRecognizer`. Garder `Anonymizer` en fallback.
2. **Backend — schéma + prompt neutre** : mettre à jour `schemas.py` (retirer
   `points_de_vigilance`/`resume`, ajouter `capital_indemnite`,
   `franchises_globales`, `montants_cles`) et `prompt.py`.
3. **Backend — orientation** : nouveau `services/orientation.py` (règles
   déterministes) + enrichissement de la réponse de `/audit`.
4. **Front — drop zone** : section « Audit de contrat » dans `index.html`,
   drag & drop, validation, appel `POST /audit`, affichage du relevé.
5. **Front — CTA d'orientation** : boutons qui appellent `setLetter()` /
   `selectType()` existants.
6. **Paywall** : feature flag `AUDIT_ENABLED`, puis (plus tard) Stripe.
7. **Conformité** : DPIA, consentement, information, remplacement DeepSeek par
   un LLM UE, suppression éphémère du contrat.

## 10. RGPD — points de vigilance (module payant = exigence renforcée)

- **Hébergement UE** + suppression immédiate du PDF après traitement.
- **DeepSeek (Chine, hors UE)** : à remplacer par Mistral/Llama pour un produit
  payant — le code le permet déjà (changement de `DEEPSEEK_BASE_URL`/`MODEL`).
- **DPIA + consentement explicite + information** (durée de rétention, droit
  d'effacement) avant l'activation commerciale.
- **Disclaimer côté front** : « relevé indicatif, ne constitue pas un conseil
  juridique » (cohérent avec les mentions légales existantes).
