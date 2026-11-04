"""Point d'entrée FastAPI du backend ProIndemni.

Lancement : `uvicorn app.main:app --reload` (depuis le dossier `backend/`).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import AppError, InvalidFileTypeError, UploadTooLargeError
from app.schemas import AuditResponse, Orientation, TextInput
from app.schemas_cgv import CgvOrientation, CgvResponse
from app.services.audit import AuditService
from app.services.audit_cgv import CgvService
from app.services.orientation import orienter
from app.services.orientation_cgv import orienter_cgv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("proindemni")

settings = get_settings()

app = FastAPI(title="ProIndemni — Audit de contrat multirisque pro", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    # `or ["*"]` : si CORS_ORIGINS est vide (ou mal renseigné en prod), on ne
    # laisse jamais la liste vide — sans quoi aucune réponse ne porterait l'en-tête
    # Access-Control-Allow-Origin et le front (proindemni.fr) serait bloqué.
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _ensure_cors_on_errors(request: Request, call_next):
    """Filet de sécurité : garantit l'en-tête CORS sur *toutes* les réponses.

    Selon la version de Starlette, les réponses produites par les handlers
    d'exception (PDF scanné → 422, erreur interne → 500) peuvent contourner le
    CORSMiddleware et partir sans Access-Control-Allow-Origin. Sans cet en-tête,
    le navigateur masque le corps de la réponse et le front ne peut pas afficher
    le message d'erreur utile. On l'ajoute donc ici, sans doublon.
    """
    response = await call_next(request)
    if "access-control-allow-origin" not in response.headers:
        response.headers["access-control-allow-origin"] = "*"
    return response

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 Mo

# Le service est construit à la première requête : si la clé API est absente,
# le démarrage ne plante pas et `/health` le signale clairement.
_service: AuditService | None = None
_cgv_service: CgvService | None = None


def _get_service() -> AuditService:
    global _service
    if _service is None:
        _service = AuditService(settings)
    return _service


def _get_cgv_service() -> CgvService:
    global _cgv_service
    if _cgv_service is None:
        _cgv_service = CgvService(settings)
    return _cgv_service


@app.exception_handler(AppError)
async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def _unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur interne non gérée : %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Erreur interne."}},
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Renvoie les erreurs de validation (ex. champ `file` manquant) en JSON lisible,
    au même format `{"error": {...}}` que les autres erreurs — et non le `{"detail": [...]}`
    par défaut de FastAPI que le front ne sait pas lire."""
    errors = exc.errors() or []
    first = errors[0] if errors else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    message = f"Champ « {loc} » invalide : {first.get('msg', 'requête invalide')}" if loc else "Requête invalide."
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": message}},
    )


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "llm_configured": settings.is_configured,
        "model": settings.deepseek_model if settings.is_configured else None,
    }


@app.post("/audit", response_model=AuditResponse)
async def audit_pdf(file: UploadFile = File(...)) -> AuditResponse:
    """Reçoit un PDF de contrat, renvoie l'audit factuel + l'aiguillage."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError("Seuls les fichiers PDF sont acceptés.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError("Fichier trop volumineux (max 25 Mo).")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        audit = await _get_service().audit_file(tmp_path)
        return AuditResponse(audit=audit, orientation=Orientation(**orienter(audit)))
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@app.post("/audit/text", response_model=AuditResponse)
async def audit_text(payload: TextInput) -> AuditResponse:
    """Audite un texte brut (endpoint de développement / tests sans PDF)."""
    audit = await _get_service().audit_text(payload.text)
    return AuditResponse(audit=audit, orientation=Orientation(**orienter(audit)))


@app.post("/audit/cgv", response_model=CgvResponse)
async def audit_cgv_pdf(file: UploadFile = File(...)) -> CgvResponse:
    """Reçoit un PDF de CGV fournisseur, renvoie la lecture factuelle + la
    checklist de négociation (déterministe, sans avis)."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError("Seuls les fichiers PDF sont acceptés.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError("Fichier trop volumineux (max 25 Mo).")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        resultat = await _get_cgv_service().audit_file(tmp_path)
        return CgvResponse(
            resultat=resultat, orientation=CgvOrientation(**orienter_cgv(resultat))
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


@app.post("/audit/cgv/text", response_model=CgvResponse)
async def audit_cgv_text(payload: TextInput) -> CgvResponse:
    """Lit un texte brut de CGV (endpoint de développement / tests)."""
    resultat = await _get_cgv_service().audit_text(payload.text)
    return CgvResponse(
        resultat=resultat, orientation=CgvOrientation(**orienter_cgv(resultat))
    )
