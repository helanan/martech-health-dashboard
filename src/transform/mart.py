"""
Transform layer: reads from MongoDB Data Vault, produces analytics documents,
writes to Elasticsearch (Information Mart).
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from src.cache.client import CacheClient
from src.search.client import SearchClient
from src.vault.repository import VaultRepository

log = structlog.get_logger()

_CACHE_TTL = 60  # seconds for transform result cache


class MartTransformer:
    def __init__(
        self,
        repo: VaultRepository,
        search: SearchClient,
        cache: CacheClient,
    ) -> None:
        self._repo = repo
        self._search = search
        self._cache = cache

    async def build_customer_event_mart(self, customer_hk: str) -> dict[str, Any]:
        """
        Aggregate a customer's events from vault satellites and push to ES.
        Uses Redis to avoid re-processing unchanged customers.
        """
        cache_key = f"mart:customer:{customer_hk}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        # Join hub_customer → link_event_customer → sat_event_payload
        pipeline = [
            {"$match": {"customer_hk": customer_hk}},
            {
                "$lookup": {
                    "from": "sat_event_payload",
                    "localField": "event_hk",
                    "foreignField": "event_hk",
                    "as": "events",
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "customer_hk": 1,
                    "events": {
                        "$map": {
                            "input": "$events",
                            "as": "e",
                            "in": {
                                "event_hk": "$$e.event_hk",
                                "event_type": "$$e.event_type",
                                "properties": "$$e.properties",
                                "load_dts": "$$e.load_dts",
                            },
                        }
                    },
                }
            },
        ]
        results = await self._repo.aggregate("link_event_customer", pipeline)
        mart_doc = {
            "customer_hk": customer_hk,
            "event_count": sum(len(r.get("events", [])) for r in results),
            "events": [e for r in results for e in r.get("events", [])],
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Push to ES
        await self._search.index_doc("customer_event_mart", customer_hk, mart_doc)

        # Cache result
        await self._cache.set(cache_key, mart_doc, ttl=_CACHE_TTL)
        log.info("mart.built", customer_hk=customer_hk, events=mart_doc["event_count"])
        return mart_doc
