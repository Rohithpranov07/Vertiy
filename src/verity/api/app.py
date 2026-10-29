"""FastAPI app: POST /check, POST /feedback, GET /health (and GET /radar, added in T7.3)."""

import logging
from datetime import UTC, datetime

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from verity import db
from verity.bn.network import LEARNED_FILE
from verity.clients.factcheck import read_ingest_status
from verity.config import get_settings
from verity.cues.tone import MODEL_FILE
from verity.errors import DataError, ExternalServiceError, InputError, ModelError, VerityError
from verity.pipeline import Pipeline, get_pipeline
from verity.rumour import radar
from verity.schemas import (
    Ack,
    CheckRequest,
    FeedbackRequest,
    HealthResponse,
    RadarItem,
    VerdictRecord,
)

STATUS: dict[type[VerityError], int] = {
    InputError: 422,
    ExternalServiceError: 502,
    DataError: 500,
    ModelError: 503,
}


log = logging.getLogger(__name__)
WARNINGS_HEADER = "X-Verity-Warnings"


def health_warnings(counts_factchecks: int) -> list[str]:
    """Degraded-mode notices. The HealthResponse model is fixed, so they travel in a header."""
    s = get_settings()
    notes: list[str] = []
    if counts_factchecks == 0 or not (s.index_dir / "factchecks.idx").exists():
        notes.append("empty-index: no fact-checks available, fact_check will read none")
    if read_ingest_status() is False:
        notes.append("factcheck-cache-only: last fact-check API refresh failed, using local cache")
    if not LEARNED_FILE.exists():
        notes.append("cpt-priors-only: no learned CPTs, using expert priors")
    if not (s.index_dir / MODEL_FILE).exists():
        notes.append("no-tone-model: using the style score alone")
    return notes


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="VERITY", version="0.1.0")

    def pipe() -> Pipeline:
        return pipeline or get_pipeline()

    @app.exception_handler(VerityError)
    async def verity_error(_: Request, exc: VerityError) -> JSONResponse:
        return _error(STATUS.get(type(exc), 500), exc.code, exc.message)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        # log the class only: exception text could contain fragments of the message
        log.error("unhandled error: %s", type(exc).__name__)
        return _error(500, "internal_error", "an unexpected error occurred")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # report which fields are wrong, never echo the submitted values
        fields = ", ".join(".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors())
        return _error(422, "invalid_request", f"invalid request fields: {fields}")

    @app.post("/check", response_model=VerdictRecord)
    def check(request: CheckRequest) -> VerdictRecord:
        return pipe().check(request)

    @app.post("/feedback", response_model=Ack)
    def feedback(request: FeedbackRequest) -> Ack:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with db.session() as conn:
            db.init_db(conn)
            db.add_feedback(conn, request.message_hash, request.verdict, request.user_label, stamp)
        return Ack(ok=True)

    @app.get("/health", response_model=HealthResponse)
    def health(response: Response) -> HealthResponse:
        with db.session() as conn:
            db.init_db(conn)
            counts = db.health_counts(conn)
        notes = health_warnings(counts.factchecks)
        if notes:
            response.headers[WARNINGS_HEADER] = "; ".join(notes)
        return HealthResponse(**counts.model_dump())

    @app.get("/radar", response_model=list[RadarItem])
    def radar_list(
        window_hours: int | None = Query(default=None, ge=1, le=24 * 30),
        limit: int | None = Query(default=None, ge=1, le=100),
    ) -> list[RadarItem]:
        with db.session() as conn:
            db.init_db(conn)
            return radar.top(conn, window_hours, limit)

    return app


app = create_app()
