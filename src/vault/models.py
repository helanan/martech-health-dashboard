"""
Data Vault 2.0 document models for MongoDB.

Hub  — business keys (immutable identity)
Link — relationships between hubs
Sat  — descriptive attributes (append-only, timestamped)
"""

from datetime import datetime, timezone
from typing import Any
import hashlib

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_key(*business_keys: str) -> str:
    """Deterministic SHA-256 hash key from one or more business key values."""
    raw = "|".join(business_keys).encode()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Hub
# ---------------------------------------------------------------------------

class HubCustomer(BaseModel):
    """Hub: unique customer identity."""
    _id: str  # hash_key(customer_id)
    customer_id: str
    load_dts: datetime = Field(default_factory=_now)
    record_source: str


class HubCampaign(BaseModel):
    _id: str
    campaign_id: str
    load_dts: datetime = Field(default_factory=_now)
    record_source: str


class HubEvent(BaseModel):
    _id: str
    event_id: str
    load_dts: datetime = Field(default_factory=_now)
    record_source: str


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------

class LinkCustomerCampaign(BaseModel):
    """Link: customer ↔ campaign interaction."""
    _id: str  # hash_key(customer_hk, campaign_hk)
    customer_hk: str
    campaign_hk: str
    load_dts: datetime = Field(default_factory=_now)
    record_source: str


class LinkEventCustomer(BaseModel):
    _id: str
    event_hk: str
    customer_hk: str
    load_dts: datetime = Field(default_factory=_now)
    record_source: str


# ---------------------------------------------------------------------------
# Satellite
# ---------------------------------------------------------------------------

class SatCustomerProfile(BaseModel):
    """Satellite: customer descriptive attributes (append-only)."""
    customer_hk: str
    load_dts: datetime = Field(default_factory=_now)
    load_end_dts: datetime | None = None
    hash_diff: str  # hash of payload to detect changes
    record_source: str
    # payload
    email: str | None = None
    name: str | None = None
    channel: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SatCampaignDetails(BaseModel):
    campaign_hk: str
    load_dts: datetime = Field(default_factory=_now)
    load_end_dts: datetime | None = None
    hash_diff: str
    record_source: str
    name: str | None = None
    channel: str | None = None
    budget: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SatEventPayload(BaseModel):
    event_hk: str
    load_dts: datetime = Field(default_factory=_now)
    hash_diff: str
    record_source: str
    event_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
