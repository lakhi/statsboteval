"""App factory. Run: uvicorn 'app.main:create_app' --factory"""

import json
import logging
import time
from typing import Any, Protocol

import jsonschema
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .blob_source import BlobAggregatesSource
from .config import Settings

logger = logging.getLogger(__name__)


class AggregatesSource(Protocol):
    def fetch(self) -> bytes | None: ...


def create_app(settings: Settings | None = None, source: AggregatesSource | None = None) -> FastAPI:
    settings = settings or Settings()
    source = source or BlobAggregatesSource(settings)
    schema = json.loads(settings.schema_path.read_text())

    app = FastAPI(title="StatsBotEval aggregates API")
    # The aggregates document is one large JSON body that every page load pulls in full,
    # and it was going over the wire uncompressed — nothing in this app or in front of it
    # was compressing it. It is highly repetitive (dense weekly series, the 7x24 activity
    # grids still published though nothing has rendered them since D-54, the same cell
    # shapes throughout) and gzips to about 6% of its size. Also covers the static bundle
    # mounted below.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    cache: dict[str, Any] = {"doc": None, "at": 0.0}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/aggregates")
    def aggregates() -> JSONResponse:
        now = time.monotonic()
        if cache["doc"] is not None and now - cache["at"] < settings.cache_ttl_seconds:
            return JSONResponse(cache["doc"])
        raw = source.fetch()
        if raw is None:
            raise HTTPException(status_code=503, detail="aggregates not yet published")
        doc = json.loads(raw)
        try:
            # Read-time tripwire (contract §11): never serve a document the schema rejects.
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as exc:
            logger.error("published aggregates failed schema validation: %s", exc.message)
            raise HTTPException(status_code=500, detail="aggregates document failed validation") from exc
        cache["doc"], cache["at"] = doc, now
        return JSONResponse(doc)

    # D-26: the API serves the dashboard's static export. Mounted after the routes
    # above, so /healthz and /api/v1/* always win; without a dist dir it's API-only.
    if settings.dashboard_dist and settings.dashboard_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.dashboard_dist, html=True), name="dashboard")

    return app
