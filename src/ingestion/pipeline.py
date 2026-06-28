"""Raw event ingestion → Data Vault loader."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import structlog

from src.vault.models import (
    HubCustomer,
    HubEvent,
    LinkEventCustomer,
    SatEventPayload,
    hash_key,
)
from src.vault.repository import VaultRepository

log = structlog.get_logger()


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.md5(serialized).hexdigest()


class EventIngestionPipeline:
    """
    Accepts a raw event dict, writes Hub/Link/Satellite records to MongoDB.
    Expected raw event shape:
        {
            "event_id": str,
            "customer_id": str,
            "event_type": str,
            "properties": dict,
            "source": str,
        }
    """

    def __init__(self, repo: VaultRepository) -> None:
        self._repo = repo

    async def ingest(self, raw: dict[str, Any]) -> None:
        source = raw.get("source", "unknown")
        now = datetime.now(timezone.utc)

        customer_hk = hash_key(raw["customer_id"])
        event_hk = hash_key(raw["event_id"])
        link_hk = hash_key(customer_hk, event_hk)

        # ── Hubs ──────────────────────────────────────────────────────
        await self._repo.upsert_hub(
            "hub_customer",
            {"_id": customer_hk, "customer_id": raw["customer_id"],
             "load_dts": now, "record_source": source},
        )
        await self._repo.upsert_hub(
            "hub_event",
            {"_id": event_hk, "event_id": raw["event_id"],
             "load_dts": now, "record_source": source},
        )

        # ── Link ──────────────────────────────────────────────────────
        await self._repo.upsert_link(
            "link_event_customer",
            {"_id": link_hk, "event_hk": event_hk, "customer_hk": customer_hk,
             "load_dts": now, "record_source": source},
        )

        # ── Satellite ─────────────────────────────────────────────────
        payload = {"event_type": raw["event_type"], "properties": raw.get("properties", {})}
        sat = {
            "event_hk": event_hk,
            "load_dts": now,
            "hash_diff": _hash_payload(payload),
            "record_source": source,
            **payload,
        }
        inserted = await self._repo.insert_satellite("sat_event_payload", sat)

        log.info("event.ingested", event_id=raw["event_id"], new_satellite=inserted)
