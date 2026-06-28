"""Elasticsearch client — index, search, and aggregation helpers."""

from typing import Any

from elasticsearch import AsyncElasticsearch
import structlog

from src.config import settings

log = structlog.get_logger()


def _index(name: str) -> str:
    return f"{settings.es_index_prefix}_{name}"


class SearchClient:
    def __init__(self) -> None:
        kwargs: dict[str, Any] = {"hosts": settings.es_hosts}
        if settings.es_api_key:
            kwargs["api_key"] = settings.es_api_key
        self._es = AsyncElasticsearch(**kwargs)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    async def ensure_index(self, name: str, mappings: dict) -> None:
        idx = _index(name)
        if not await self._es.indices.exists(index=idx):
            await self._es.indices.create(index=idx, mappings=mappings)
            log.info("es.index_created", index=idx)

    # ------------------------------------------------------------------
    # Document ops
    # ------------------------------------------------------------------

    async def index_doc(self, index_name: str, doc_id: str, doc: dict) -> None:
        await self._es.index(index=_index(index_name), id=doc_id, document=doc)

    async def bulk_index(self, index_name: str, docs: list[dict]) -> None:
        """docs must include '_id' field."""
        operations: list[dict] = []
        for doc in docs:
            doc_id = doc.pop("_id")
            operations.append({"index": {"_index": _index(index_name), "_id": doc_id}})
            operations.append(doc)
        if operations:
            await self._es.bulk(operations=operations)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        index_name: str,
        query: dict,
        aggs: dict | None = None,
        size: int = 50,
        from_: int = 0,
    ) -> dict:
        body: dict[str, Any] = {"query": query, "size": size, "from": from_}
        if aggs:
            body["aggs"] = aggs
        resp = await self._es.search(index=_index(index_name), body=body)
        return resp.body

    async def knn_search(
        self,
        index_name: str,
        field: str,
        query_vector: list[float],
        k: int = 10,
        num_candidates: int = 100,
    ) -> dict:
        """Approximate nearest-neighbour (vector search) via ES kNN API."""
        resp = await self._es.search(
            index=_index(index_name),
            knn={"field": field, "query_vector": query_vector,
                 "k": k, "num_candidates": num_candidates},
        )
        return resp.body

    async def close(self) -> None:
        await self._es.close()
