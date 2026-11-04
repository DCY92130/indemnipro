# Image du backend ProIndemni (FastAPI + Presidio + spaCy).
# Portable : fonctionne sur Render, Scaleway, Fly.io, ou tout hébergeur de conteneurs.
#
# Le modèle spaCy est choisi au build via --build-arg :
#   docker build --build-arg SPACY_MODEL=fr_core_news_md .
#   · fr_core_news_md (~45 Mo)  → recommandé pour l'hébergement (image légère)
#   · fr_core_news_lg (571 Mo)  → qualité max, image lourde, réservé au local
FROM python:3.12-slim

ARG SPACY_MODEL=fr_core_news_md
ENV SPACY_MODEL=${SPACY_MODEL} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Couche pip mise en cache tant que requirements.txt ne change pas.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Modèle spaCy français (hors pip, téléchargé une fois au build).
RUN python -m spacy download ${SPACY_MODEL}

# Code applicatif.
COPY app ./app
COPY cli.py .

EXPOSE 8000

# uvicorn démarre le serveur ; la clé LLM vient de l'environnement (jamais de l'image).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
