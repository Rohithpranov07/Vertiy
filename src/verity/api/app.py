"""FastAPI app: POST /check, POST /feedback, GET /health (and GET /radar, added in T7.3)."""

from datetime import UTC, datetime

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from verity import db
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


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="VERITY", version="0.1.0")

    def pipe() -> Pipeline:
        return pipeline or get_pipeline()

    @app.exception_handler(VerityError)
    async def verity_error(_: Request, exc: VerityError) -> JSONResponse:
        return _error(STATUS.get(type(exc), 500), exc.code, exc.message)

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
    def health() -> HealthResponse:
        with db.session() as conn:
            db.init_db(conn)
            counts = db.health_counts(conn)
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
