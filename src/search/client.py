"""OpenSearch client — index, search, and aggregation helpers."""

from typing import Any

from opensearchpy import AsyncOpenSearch
import structlog

from src.config import settings

log = structlog.get_logger()


def _index(name: str) -> str:
    return f"{settings.es_index_prefix}_{name}"


class SearchClient:
    def __init__(self) -> None:
        raw_hosts = [h.strip() for h in settings.es_hosts.split(",")]
        use_ssl = any(h.startswith("https://") for h in raw_hosts)
        hosts = [h.replace("https://", "").replace("http://", "") for h in raw_hosts]
        self._os = AsyncOpenSearch(
            hosts=hosts,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            ssl_show_warn=False,
            http_compress=True,
        )

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    async def ensure_index(self, name: str, mappings: dict) -> None:
        idx = _index(name)
        if not await self._os.indices.exists(index=idx):
            await self._os.indices.create(index=idx, body={"mappings": mappings})
            log.info("os.index_created", index=idx)

    # ------------------------------------------------------------------
    # Document ops
    # ------------------------------------------------------------------

    async def index_doc(self, index_name: str, doc_id: str, doc: dict) -> None:
        await self._os.index(index=_index(index_name), id=doc_id, body=doc)

    async def bulk_index(self, index_name: str, docs: list[dict]) -> None:
        operations: list[dict] = []
        for doc in docs:
            doc_id = doc.pop("_id")
            operations.append({"index": {"_index": _index(index_name), "_id": doc_id}})
            operations.append(doc)
        if operations:
            await self._os.bulk(body=operations)

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
        resp = await self._os.search(index=_index(index_name), body=body)
        return resp

    async def knn_search(
        self,
        index_name: str,
        field: str,
        query_vector: list[float],
        k: int = 10,
    ) -> dict:
        """k-NN vector search via OpenSearch kNN plugin."""
        body = {"query": {"knn": {field: {"vector": query_vector, "k": k}}}}
        resp = await self._os.search(index=_index(index_name), body=body)
        return resp

    async def close(self) -> None:
        await self._os.close()
