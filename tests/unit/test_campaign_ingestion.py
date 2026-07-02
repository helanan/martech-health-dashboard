from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ingestion.campaign_pipeline import CampaignIngestionPipeline


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.upsert_hub = AsyncMock()
    repo.upsert_link = AsyncMock()
    repo.insert_satellite = AsyncMock(return_value=True)
    return repo


@pytest.mark.asyncio
async def test_ingest_creates_three_hubs(mock_repo):
    pipeline = CampaignIngestionPipeline(mock_repo)
    await pipeline.ingest({
        "interaction_id": "int_001",
        "customer_id": "cust_001",
        "campaign_id": "camp_001",
        "interaction_type": "impression",
        "properties": {},
        "source": "ad_network",
    })
    assert mock_repo.upsert_hub.call_count == 3  # customer + campaign + interaction


@pytest.mark.asyncio
async def test_ingest_creates_two_links(mock_repo):
    pipeline = CampaignIngestionPipeline(mock_repo)
    await pipeline.ingest({
        "interaction_id": "int_002",
        "customer_id": "cust_001",
        "campaign_id": "camp_001",
        "interaction_type": "click",
        "properties": {},
        "source": "ad_network",
    })
    assert mock_repo.upsert_link.call_count == 2  # customer↔campaign + interaction↔campaign


@pytest.mark.asyncio
async def test_ingest_with_campaign_details(mock_repo):
    pipeline = CampaignIngestionPipeline(mock_repo)
    await pipeline.ingest({
        "interaction_id": "int_003",
        "customer_id": "cust_001",
        "campaign_id": "camp_001",
        "interaction_type": "conversion",
        "properties": {"revenue": 99.0},
        "campaign_name": "Summer Sale",
        "channel": "email",
        "budget": 5000.0,
        "source": "crm",
    })
    # 2 satellites: interaction payload + campaign details
    assert mock_repo.insert_satellite.call_count == 2


@pytest.mark.asyncio
async def test_ingest_without_campaign_details(mock_repo):
    pipeline = CampaignIngestionPipeline(mock_repo)
    await pipeline.ingest({
        "interaction_id": "int_004",
        "customer_id": "cust_002",
        "campaign_id": "camp_002",
        "interaction_type": "impression",
        "properties": {},
        "source": "display",
    })
    # Only 1 satellite: interaction payload (no campaign details provided)
    assert mock_repo.insert_satellite.call_count == 1
