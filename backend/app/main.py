import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response

from app.api import api_router
from app.config import get_settings
from app.health import HealthResponse, ServiceCheck, get_checks, run_checks
from app.storage import ensure_bucket, make_s3_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.s3_create_bucket:
        try:
            if ensure_bucket(make_s3_client(settings), settings.s3_bucket):
                logger.info("Created bucket %s", settings.s3_bucket)
        except Exception as exc:  # noqa: BLE001 - health endpoint will report it
            logger.warning("Could not ensure bucket: %s", type(exc).__name__)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Maestro Especiais API", version="0.0.1", lifespan=lifespan)

    @app.get("/api/health")
    def health(
        response: Response,
        checks: Annotated[dict[str, ServiceCheck], Depends(get_checks)],
    ) -> HealthResponse:
        result = run_checks(checks)
        response.status_code = 200 if result.status == "ok" else 503
        return result

    app.include_router(api_router)
    return app


app = create_app()
