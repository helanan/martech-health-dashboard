"""FastAPI application — ingestion, search, and mart endpoints."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import structlog

from src.cache.client import CacheClient
from src.config import settings
from src.ingestion.pipeline import EventIngestionPipeline
from src.search.client import SearchClient
from src.transform.mart import MartTransformer
from src.vault.repository import VaultRepository

log = structlog.get_logger()

_mongo: AsyncIOMotorClient | None = None
_repo: VaultRepository | None = None
_cache: CacheClient | None = None
_search: SearchClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _mongo, _repo, _cache, _search
    _mongo = AsyncIOMotorClient(settings.mongo_uri)
    _repo = VaultRepository(_mongo)
    _cache = CacheClient()
    _search = SearchClient()

    try:
        await _search.ensure_index(
            "customer_event_mart",
            mappings={
                "properties": {
                    "customer_hk": {"type": "keyword"},
                    "event_count": {"type": "integer"},
                    "refreshed_at": {"type": "date"},
                    "events": {"type": "object", "enabled": False},
                }
            },
        )
    except Exception as e:
        log.warning("opensearch.unavailable_at_startup", error=str(e))
    log.info("app.started")
    yield
    if _mongo:
        _mongo.close()
    if _cache:
        await _cache.close()
    if _search:
        await _search.close()
    log.info("app.stopped")


app = FastAPI(title="Martech Pipeline", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class IngestEventRequest(BaseModel):
    event_id: str
    customer_id: str
    event_type: str
    properties: dict[str, Any] = {}
    source: str = "api"


class SearchRequest(BaseModel):
    query: dict[str, Any]
    aggs: dict[str, Any] | None = None
    size: int = 50
    from_: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/ingest/event", status_code=202)
async def ingest_event(req: IngestEventRequest) -> dict:
    pipeline = EventIngestionPipeline(_repo)  # type: ignore[arg-type]
    await pipeline.ingest(req.model_dump())
    return {"status": "accepted", "event_id": req.event_id}


@app.get("/mart/customer/{customer_id}")
async def get_customer_mart(customer_id: str) -> dict:
    from src.vault.models import hash_key
    customer_hk = hash_key(customer_id)
    transformer = MartTransformer(_repo, _search, _cache)  # type: ignore[arg-type]
    return await transformer.build_customer_event_mart(customer_hk)


@app.post("/search/{index_name}")
async def search_index(index_name: str, req: SearchRequest) -> dict:
    result = await _search.search(  # type: ignore[union-attr]
        index_name, req.query, aggs=req.aggs, size=req.size, from_=req.from_
    )
    return result


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
