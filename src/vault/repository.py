"""MongoDB Data Vault repository — upsert-only, append-only satellites."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.config import settings


class VaultRepository:
    def __init__(self, client: AsyncIOMotorClient) -> None:
        self._db: AsyncIOMotorDatabase = client[settings.mongo_db]

    # ------------------------------------------------------------------
    # Hub upserts (idempotent on _id = hash key)
    # ------------------------------------------------------------------

    async def upsert_hub(self, collection: str, doc: dict) -> None:
        await self._db[collection].update_one(
            {"_id": doc["_id"]},
            {"$setOnInsert": doc},
            upsert=True,
        )

    # ------------------------------------------------------------------
    # Satellite inserts (append-only; skip if hash_diff unchanged)
    # ------------------------------------------------------------------

    async def insert_satellite(self, collection: str, doc: dict) -> bool:
        """Insert a new satellite record only when payload changed."""
        existing = await self._db[collection].find_one(
            {
                "customer_hk" if "customer_hk" in doc else "campaign_hk"
                if "campaign_hk" in doc
                else "event_hk": doc.get(
                    "customer_hk", doc.get("campaign_hk", doc.get("event_hk"))
                ),
                "load_end_dts": None,
            },
            sort=[("load_dts", -1)],
        )
        if existing and existing.get("hash_diff") == doc["hash_diff"]:
            return False  # no change
        await self._db[collection].insert_one(doc)
        return True

    # ------------------------------------------------------------------
    # Link upserts
    # ------------------------------------------------------------------

    async def upsert_link(self, collection: str, doc: dict) -> None:
        await self._db[collection].update_one(
            {"_id": doc["_id"]},
            {"$setOnInsert": doc},
            upsert=True,
        )

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    async def aggregate(self, collection: str, pipeline: list) -> list[dict]:
        cursor = self._db[collection].aggregate(pipeline)
        return await cursor.to_list(length=None)

    async def find(self, collection: str, query: dict, limit: int = 100) -> list[dict]:
        cursor = self._db[collection].find(query).limit(limit)
        return await cursor.to_list(length=limit)
