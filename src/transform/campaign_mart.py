"""
Campaign mart transformer: aggregates vault → ES campaign performance index.

Produces a per-campaign document with impression/click/conversion counts,
revenue, and a breakdown by customer.
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from src.cache.client import CacheClient
from src.search.client import SearchClient
from src.vault.repository import VaultRepository

log = structlog.get_logger()

_CACHE_TTL = 120


class CampaignMartTransformer:
    def __init__(
        self,
        repo: VaultRepository,
        search: SearchClient,
        cache: CacheClient,
    ) -> None:
        self._repo = repo
        self._search = search
        self._cache = cache

    async def build_campaign_mart(self, campaign_hk: str) -> dict[str, Any]:
        cache_key = f"mart:campaign:{campaign_hk}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        # Aggregate interactions for this campaign
        pipeline = [
            {"$match": {"campaign_hk": campaign_hk}},
            {
                "$group": {
                    "_id": "$interaction_type",
                    "count": {"$sum": 1},
                    "revenue": {
                        "$sum": {"$ifNull": ["$properties.revenue", 0]}
                    },
                    "unique_customers": {"$addToSet": "$customer_hk"},
                }
            },
        ]
        interaction_stats = await self._repo.aggregate(  # type: ignore[arg-type]
            "sat_campaign_interaction", pipeline
        )

        # Pull campaign details satellite
        details_list = await self._repo.find(
            "sat_campaign_details",
            {"campaign_hk": campaign_hk, "load_end_dts": None},
            limit=1,
        )
        details = details_list[0] if details_list else {}

        # Build summary
        summary: dict[str, Any] = {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "total_revenue": 0.0,
            "unique_customers": 0,
        }
        all_customers: set[str] = set()
        breakdown: list[dict] = []

        for stat in interaction_stats:
            itype = stat["_id"]
            count = stat["count"]
            revenue = stat.get("revenue", 0.0)
            customers = stat.get("unique_customers", [])
            all_customers.update(customers)

            if itype == "impression":
                summary["impressions"] = count
            elif itype == "click":
                summary["clicks"] = count
            elif itype == "conversion":
                summary["conversions"] = count
                summary["total_revenue"] += revenue

            breakdown.append({
                "interaction_type": itype,
                "count": count,
                "revenue": revenue,
                "unique_customers": len(customers),
            })

        summary["unique_customers"] = len(all_customers)
        summary["ctr"] = (
            round(summary["clicks"] / summary["impressions"], 4)
            if summary["impressions"] > 0 else 0.0
        )
        summary["cvr"] = (
            round(summary["conversions"] / summary["clicks"], 4)
            if summary["clicks"] > 0 else 0.0
        )

        mart_doc = {
            "campaign_hk": campaign_hk,
            "campaign_id": details.get("name", "unknown"),
            "channel": details.get("channel"),
            "budget": details.get("budget"),
            "summary": summary,
            "breakdown": breakdown,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }

        await self._search.index_doc("campaign_mart", campaign_hk, mart_doc)
        await self._cache.set(cache_key, mart_doc, ttl=_CACHE_TTL)

        log.info(
            "campaign_mart.built",
            campaign_hk=campaign_hk,
            impressions=summary["impressions"],
            clicks=summary["clicks"],
            conversions=summary["conversions"],
            ctr=summary["ctr"],
        )
        return mart_doc
