"""Campaign ingestion → Data Vault loader.

Expected raw campaign interaction shape:
    {
        "interaction_id": str,   # unique ID for this customer↔campaign event
        "customer_id": str,
        "campaign_id": str,
        "interaction_type": str, # e.g. "impression", "click", "conversion"
        "properties": dict,      # channel, creative, revenue, etc.
        "source": str,
    }
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import structlog

from src.vault.models import hash_key
from src.vault.repository import VaultRepository

log = structlog.get_logger()


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.md5(serialized).hexdigest()


class CampaignIngestionPipeline:
    def __init__(self, repo: VaultRepository) -> None:
        self._repo = repo

    async def ingest(self, raw: dict[str, Any]) -> None:
        source = raw.get("source", "unknown")
        now = datetime.now(timezone.utc)

        customer_hk = hash_key(raw["customer_id"])
        campaign_hk = hash_key(raw["campaign_id"])
        interaction_hk = hash_key(raw["interaction_id"])
        link_cc_hk = hash_key(customer_hk, campaign_hk)
        link_ic_hk = hash_key(interaction_hk, customer_hk, campaign_hk)

        # ── Hubs ──────────────────────────────────────────────────────
        await self._repo.upsert_hub(
            "hub_customer",
            {"_id": customer_hk, "customer_id": raw["customer_id"],
             "load_dts": now, "record_source": source},
        )
        await self._repo.upsert_hub(
            "hub_campaign",
            {"_id": campaign_hk, "campaign_id": raw["campaign_id"],
             "load_dts": now, "record_source": source},
        )
        await self._repo.upsert_hub(
            "hub_interaction",
            {"_id": interaction_hk, "interaction_id": raw["interaction_id"],
             "load_dts": now, "record_source": source},
        )

        # ── Links ─────────────────────────────────────────────────────
        await self._repo.upsert_link(
            "link_customer_campaign",
            {"_id": link_cc_hk, "customer_hk": customer_hk,
             "campaign_hk": campaign_hk, "load_dts": now, "record_source": source},
        )
        await self._repo.upsert_link(
            "link_interaction_campaign",
            {"_id": link_ic_hk, "interaction_hk": interaction_hk,
             "customer_hk": customer_hk, "campaign_hk": campaign_hk,
             "load_dts": now, "record_source": source},
        )

        # ── Satellite: campaign interaction payload ────────────────────
        payload = {
            "interaction_type": raw["interaction_type"],
            "properties": raw.get("properties", {}),
        }
        sat = {
            "interaction_hk": interaction_hk,
            "customer_hk": customer_hk,
            "campaign_hk": campaign_hk,
            "load_dts": now,
            "load_end_dts": None,
            "hash_diff": _hash_payload(payload),
            "record_source": source,
            **payload,
        }
        await self._repo.insert_satellite("sat_campaign_interaction", sat)

        # ── Satellite: campaign details (upsert on change) ────────────
        if "campaign_name" in raw or "channel" in raw or "budget" in raw:
            details_payload = {
                "name": raw.get("campaign_name"),
                "channel": raw.get("channel"),
                "budget": raw.get("budget"),
            }
            details_sat = {
                "campaign_hk": campaign_hk,
                "load_dts": now,
                "load_end_dts": None,
                "hash_diff": _hash_payload(details_payload),
                "record_source": source,
                **details_payload,
            }
            await self._repo.insert_satellite("sat_campaign_details", details_sat)

        log.info(
            "campaign_interaction.ingested",
            interaction_id=raw["interaction_id"],
            campaign_id=raw["campaign_id"],
            interaction_type=raw["interaction_type"],
        )
