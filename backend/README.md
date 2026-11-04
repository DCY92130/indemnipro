# ProIndemni — Backend d'audit de contrat multirisque pro

Backend **Python / FastAPI** qui extrait le texte d'un PDF de contrat d'assurance,
le pseudonymise localement, l'envoie à un LLM (DeepSeek via le SDK OpenAI) et
renvoie un **audit structuré en JSON** (garanties, franchises, exclusions,
perte d'exploitation, délais, montants clés).

## Installation

```bash
cd backend
python -m venv .venv
# Windows :
.venv\Scripts\activate
# macOS / Linux :
source .venv/bin/activate

pip install -r requirements.txt

# Anonymisation NER (optionnelle mais recommandée — repli regex si absente) :
python -m spacy download fr_core_news_lg

cp .env.example .env   # puis renseigner DEEPSEEK_API_KEY
```

## Lancement

```bash
# Serveur HTTP
uvicorn app.main:app --reload
# → http://localhost:8000/docs

# Test en ligne de commande sur un PDF local
python cli.py ../chemin/vers/contrat.pdf
```

### Endpoints

| Méthode | Route         | Description                                                        |
|---------|---------------|--------------------------------------------------------------------|
| GET     | `/health`     | État + indique si la clé LLM est configurée                        |
| POST    | `/audit`      | Upload d'un PDF → `{ audit, orientation }` (aiguillage courrier/dossier) |
| POST    | `/audit/text` | Texte brut → `{ audit, orientation }` (dev/tests)                  |

Exemple :

```bash
curl -F "file=@contrat.pdf" http://localhost:8000/audit
```

## Configuration (`.env`)

| Variable               | Défaut                    | Rôle                                        |
|------------------------|---------------------------|---------------------------------------------|
| `DEEPSEEK_API_KEY`     | *(obligatoire)*           | Clé API                                     |
| `DEEPSEEK_BASE_URL`    | `https://api.deepseek.com`| Fournisseur LLM (voir RGPD ci-dessous)      |
| `DEEPSEEK_MODEL`       | `deepseek-chat`           | Modèle — `deepseek-reasoner` interdit ici (pas de `response_format`) |
| `DEEPSEEK_TEMPERATURE` | `0.0`                     | 0 pour un audit le plus déterministe possible |
| `LLM_TIMEOUT_SECONDS`  | `120`                     | Timeout par appel                           |
| `LLM_OUTPUT_RETRIES`   | `1`                       | Relances si le JSON de sortie est invalide  |
| `MAX_INPUT_CHARS`      | `180000`                  | Garde-fou de taille (voir limitation)       |
| `CORS_ORIGINS`         | `*`                       | Origines autorisées                         |
| `SPACY_MODEL`          | `fr_core_news_lg`         | Modèle spaCy NER — `fr_core_news_md` en hébergement léger |

## Pipeline

```
PDF ──► PdfExtractor (PyMuPDF, marqueurs « --- Page N --- »)
    ──► Anonymizer (regex : email / tel / SIRET / SIREN / IBAN / adresse / nom)
    ──► Presidio NER (fr_core_news_lg : noms/orgs/lieux en prose — repli regex)
    ──► DeepSeekClient (SDK openai, response_format=json_object)
    ──► AuditResult (validation Pydantic, relance si JSON invalide)
    ──► Orientation (règles déterministes → courrier + checklist)
```

L'aiguillage (`orientation`) est **déterministe et jamais confié au LLM** : à
partir des champs factuels de l'audit (perte d'exploitation couverte ?, exclusion
émeutes ?, vol couvert ?, délai raccourci), il renvoie le courrier et la checklist
qui conviennent (`{ courrier, checklist, raisons }`), sans émettre d'avis.
Voir `app/services/orientation.py` et `CONCEPTION-AUDIT-PAYANT.md §6`.

## ⚠️ Limites connues & conformité RGPD

1. **L'anonymisation reste une *pseudonymisation*, pas une anonymisation
   complète.** Les identifiants *structurés* (email, téléphone, SIRET/SIREN,
   IBAN, code postal) sont masqués par regex, et les noms/orgs/lieux *en prose*
   par Presidio NER (`fr_core_news_lg`) — mais un NER peut laisser des résidus
   (noms d'entreprise sans marqueur). Traitez l'intégralité du document comme
   une donnée personnelle.

2. **DeepSeek = transfert de données hors UE (Chine), sans décision d'adéquation.**
   Pour une plateforme française, la voie conforme est d'héberger un modèle
   open-weight (Mistral, Llama) chez un hébergeur UE (Scaleway, OVH, Azure France),
   ou *a minima* : DPIA + consentement explicite de l'utilisateur + information
   claire. Le code est prêt pour cela : il suffit de changer `DEEPSEEK_BASE_URL`
   et `DEEPSEEK_MODEL`, rien d'autre.

3. **Très longs contrats (80+ pages).** `deepseek-chat` accepte ~64k tokens.
   Au-delà de `MAX_INPUT_CHARS` (≈180k caractères), le texte est tronqué à une
   frontière de page **avec un avertissement** — ce qui peut faire perdre une
   clause. Pour aller plus loin, il faudrait un découpage par lots
   (map-reduce) ; ce n'est pas implémenté ici.

4. **Le LLM peut encore halluciner malgré la consigne « aucune supposition ».**
   Les garde-fous (température 0, citation de page obligatoire, schéma
   `Non mentionné dans le document`, relance sur JSON invalide) réduisent le
   risque mais ne l'annulent pas. Affichez un disclaimer « résultat indicatif,
   pas un conseil juridique » côté front.
