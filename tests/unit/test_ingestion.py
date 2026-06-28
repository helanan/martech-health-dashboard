from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ingestion.pipeline import EventIngestionPipeline


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.upsert_hub = AsyncMock()
    repo.upsert_link = AsyncMock()
    repo.insert_satellite = AsyncMock(return_value=True)
    return repo


@pytest.mark.asyncio
async def test_ingest_calls_hub_and_satellite(mock_repo):
    pipeline = EventIngestionPipeline(mock_repo)
    await pipeline.ingest(
        {
            "event_id": "evt_1",
            "customer_id": "cust_1",
            "event_type": "page_view",
            "properties": {"url": "/home"},
            "source": "web",
        }
    )
    assert mock_repo.upsert_hub.call_count == 2  # hub_customer + hub_event
    assert mock_repo.upsert_link.call_count == 1
    assert mock_repo.insert_satellite.call_count == 1


@pytest.mark.asyncio
async def test_ingest_idempotent_satellite(mock_repo):
    mock_repo.insert_satellite = AsyncMock(return_value=False)  # no change
    pipeline = EventIngestionPipeline(mock_repo)
    raw = {
        "event_id": "evt_2",
        "customer_id": "cust_2",
        "event_type": "click",
        "properties": {},
        "source": "web",
    }
    await pipeline.ingest(raw)
    await pipeline.ingest(raw)
    assert mock_repo.insert_satellite.call_count == 2
