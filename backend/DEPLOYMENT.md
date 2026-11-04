# Déploiement du backend ProIndemni

Le backend est une app **FastAPI** conteneurisée (`Dockerfile`). Il tourne tel quel
sur n'importe quel hébergeur de conteneurs. Le choix de l'hébergeur est **votre
décision** : c'est votre identité, votre carte bancaire et votre clé API qui créent
le compte — je ne peux pas le faire à votre place. Tout le reste (config, image,
push GitHub, étapes) est prêt ci-dessous.

> ⚠️ **RGPD** : le backend traite des contrats d'assurance (données sensibles) et
> appelle DeepSeek (Chine, pas de décision d'adéquation — cf. `README.md`). Pour une
> mise en production conforme, visez un hébergeur **UE** (Scaleway/OVH) et remplacez
> à terme le LLM par un modèle open-weight hébergé en UE (étape 7 du plan). Render
> (US) est un bon **test rapide**, pas une cible de prod.

## Ce qui est déjà prêt (fait pour vous)

- `Dockerfile` — image portable, modèle spaCy choisi au build.
- `.dockerignore` — exclut `.env`, `.venv`, PDF, artefacts.
- `render.yaml` — blueprint de déploiement Docker (chemin rapide).
- Le modèle spaCy est **configurable** via la variable d'env `SPACY_MODEL`
  (`fr_core_news_md` recommandé en hébergement, `fr_core_news_lg` en local).

## Prérequis unique (à faire une fois, par vous)

Pousser le backend sur GitHub (déjà votre dépôt `DCY92130/indemnipro`) :

```bash
git add backend
git commit -m "feat : backend d'audit FastAPI (anonymisation + extraction + orientation)"
git push
```

## Chemin A — Render (le plus rapide, ~5 min, hors UE)

1. Créez un compte sur https://render.com (GitHub login).
2. Dashboard → **New +** → **Blueprint**, connectez le repo `DCY92130/indemnipro`.
3. Render lit `backend/render.yaml` automatiquement et crée le service.
4. Dashboard → service `proindemni-backend` → **Environment** → renseignez
   `DEEPSEEK_API_KEY` (votre clé). `SPACY_MODEL` est déjà `fr_core_news_md`.
5. Attendez le build (~3-5 min : pip + téléchargement du modèle) puis ouvrez
   l'URL affichée → `/health` doit répondre `{"status":"ok","llm_configured":true}`.
6. Testez : `curl -F "file=@contrat.pdf" https://VOTRE-URL.onrender.com/audit`.

Limite : le plan gratuit/Starter a un *cold start* (l'instance se coupe après
inactivité et redémarre ~30-50 s à la première requête). C'est un serveur US.

## Chemin B — Scaleway (recommandé en prod, hébergement UE)

1. Créez un compte https://www.scaleway.com (France, facturation en UE).
2. **Container Registry** → créez un namespace, puis poussez l'image :

   ```bash
   docker build -t proindemni-backend .
   docker tag proindemni-backend rg.fr-par.scw.cloud/<namespace>/proindemni-backend:latest
   docker login rg.fr-par.scw.cloud -u nologin -p "$SCW_SECRET_KEY"
   docker push rg.fr-par.scw.cloud/<namespace>/proindemni-backend:latest
   ```

3. **Serverless Containers** (ou **Kubernetes Kapsule** si trafic régulier) →
   **Create container** → sélectionnez l'image → réglez la mémoire à ~1 Go
   (spaCy charge le modèle en RAM) → port `8000` → variables d'env :
   `DEEPSEEK_API_KEY`, `SPACY_MODEL=fr_core_news_md`, `CORS_ORIGINS=*`.
4. Activez l'**HTTPS** (domaine auto `*.functions.fnc.fr-par.scw.cloud`).
5. Testez `/health` et `/audit` comme au chemin A.

## Après le déploiement

- Le frontend (`index.html`) devra pointer vers l'URL du backend : c'est l'étape
  suivante (zone de drop + appel `POST /audit` + `setLetter()`/`selectType()`),
  encore **non câblée** tant que l'URL n'existe pas.
- Le module est **désactivé par défaut** côté front (`AUDIT_ENABLED=false` prévu) :
  il ne sera activé qu'une fois le backend en ligne et le paywall (Stripe) posé.
