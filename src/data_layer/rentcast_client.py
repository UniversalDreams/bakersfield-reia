"""Thin wrapper around the RentCast API.

Phase 1 scope: enough to pull one property's AVM value + rent estimate and
cache the raw responses on disk so repeated runs during development don't
burn free-tier API calls. Refresh-cadence policy and a stricter raw/clean
split are hardened in Phase 2.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.rentcast.io/v1"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


class RentCastAuthError(RuntimeError):
    """Raised when the RentCast API rejects the configured API key."""


@dataclass
class PropertySnapshot:
    """Cleaned fields the simulation layer consumes.

    Kept separate from the raw API payloads (available via `raw`) so the
    simulation never depends on RentCast's exact response shape.
    """

    address: str
    zip_code: str | None
    property_type: str | None
    year_built: int | None
    bedrooms: float | None
    bathrooms: float | None
    square_footage: float | None
    purchase_price: float
    price_range_low: float | None
    price_range_high: float | None
    monthly_rent: float
    rent_range_low: float | None
    rent_range_high: float | None
    raw: dict[str, Any]


class RentCastClient:
    def __init__(self, api_key: str | None = None, cache_dir: Path | str = DEFAULT_CACHE_DIR):
        if api_key is None:
            load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
            api_key = os.getenv("RENTCAST_API_KEY")
        if not api_key:
            raise RuntimeError(
                "RENTCAST_API_KEY not set. Add it to .env at the project root."
            )
        self._api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, endpoint: str, params: dict[str, Any]) -> Path:
        key_material = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True)
        digest = hashlib.sha256(key_material.encode()).hexdigest()[:24]
        safe_endpoint = endpoint.strip("/").replace("/", "_")
        return self.cache_dir / f"{safe_endpoint}__{digest}.json"

    def _get(self, endpoint: str, params: dict[str, Any], use_cache: bool = True) -> Any:
        cache_path = self._cache_path(endpoint, params)
        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text())

        resp = requests.get(
            f"{BASE_URL}{endpoint}",
            headers={"X-Api-Key": self._api_key, "Accept": "application/json"},
            params=params,
            timeout=15,
        )
        if resp.status_code == 401:
            raise RentCastAuthError(
                f"RentCast rejected the API key: {resp.text[:300]}"
            )
        resp.raise_for_status()
        data = resp.json()

        cache_path.write_text(json.dumps(data))
        return data

    def search_properties(
        self,
        city: str,
        state: str,
        property_type: str | None = None,
        limit: int = 5,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"city": city, "state": state, "limit": limit}
        if property_type:
            params["propertyType"] = property_type
        return self._get("/properties", params, use_cache=use_cache)

    def get_avm_value(self, address: str, use_cache: bool = True) -> dict[str, Any]:
        return self._get("/avm/value", {"address": address}, use_cache=use_cache)

    def get_avm_rent(self, address: str, use_cache: bool = True) -> dict[str, Any]:
        return self._get("/avm/rent/long-term", {"address": address}, use_cache=use_cache)

    def get_property_snapshot(self, address: str, use_cache: bool = True) -> PropertySnapshot:
        value = self.get_avm_value(address, use_cache=use_cache)
        rent = self.get_avm_rent(address, use_cache=use_cache)
        subject = value.get("subjectProperty") or rent.get("subjectProperty") or {}

        return PropertySnapshot(
            address=subject.get("formattedAddress", address),
            zip_code=subject.get("zipCode"),
            property_type=subject.get("propertyType"),
            year_built=subject.get("yearBuilt"),
            bedrooms=subject.get("bedrooms"),
            bathrooms=subject.get("bathrooms"),
            square_footage=subject.get("squareFootage"),
            purchase_price=value["price"],
            price_range_low=value.get("priceRangeLow"),
            price_range_high=value.get("priceRangeHigh"),
            monthly_rent=rent["rent"],
            rent_range_low=rent.get("rentRangeLow"),
            rent_range_high=rent.get("rentRangeHigh"),
            raw={"value": value, "rent": rent},
        )
