"""Dedicated connectors for official Kerala, India, and Global data portals.

Provides programmatic querying for:
- World Bank Indicators REST API (open access, zero key required)
- NASA CMR (Common Metadata Repository) Earth observation search API
- data.gov.in Open Government Data Platform India catalog search
- Regional web bulletin & statistical publication extraction
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from config.logging_config import get_logger
from src.research.base import ResearchError, SearchResult

logger = get_logger("research.sources.official_connectors")

DEFAULT_TIMEOUT = 8


class WorldBankConnector:
    """Connects to the official World Bank Open Data REST API."""

    BASE_URL = "https://api.worldbank.org/v2"

    INDICATOR_MAP = {
        "agriculture": "AG.LND.AGRI.ZS",  # Agricultural land (% of land area)
        "cereal_yield": "AG.YLD.CREL.KG",  # Cereal yield (kg per hectare)
        "rural_population": "SP.RUR.TOTL.ZS",  # Rural population (% of total)
        "health_physicians": "SH.MED.PHYS.ZS",  # Physicians per 1,000 people
        "education_literacy": "SE.ADT.LITR.ZS",  # Literacy rate, adult total
        "poverty": "SI.POV.NAHC",  # Poverty headcount ratio at national poverty lines
    }

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def get_indicator(
        self,
        country: str = "IND",
        indicator: str = "AG.LND.AGRI.ZS",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch historical indicator values for a given country code (default India 'IND')."""
        indicator_code = self.INDICATOR_MAP.get(indicator, indicator)
        url = f"{self.BASE_URL}/country/{country}/indicator/{indicator_code}?format=json&per_page={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HackathonIQ/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                    return [
                        {
                            "year": row.get("date"),
                            "value": row.get("value"),
                            "indicator": row.get("indicator", {}).get("value"),
                            "country": row.get("country", {}).get("value"),
                        }
                        for row in data[1]
                        if row.get("value") is not None
                    ]
                return []
        except Exception as e:
            logger.warning("World Bank API query failed: %s", e)
            return []


class NasaCmrConnector:
    """Connects to NASA Common Metadata Repository (CMR) for Earth Observation dataset discovery."""

    BASE_URL = "https://cmr.earthdata.nasa.gov/search/collections.json"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def search_collections(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search NASA satellite and Earth science collections by keyword."""
        encoded_kw = urllib.parse.quote(keyword)
        url = f"{self.BASE_URL}?keyword={encoded_kw}&page_size={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HackathonIQ/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                entries = data.get("feed", {}).get("entry", [])
                results = []
                for entry in entries:
                    results.append(
                        {
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "summary": entry.get("summary", "")[:300],
                            "time_start": entry.get("time_start"),
                            "data_center": entry.get("data_center"),
                            "archive_center": entry.get("archive_center"),
                        }
                    )
                return results
        except Exception as e:
            logger.warning("NASA CMR query failed: %s", e)
            return []


class DataGovInConnector:
    """Connects to data.gov.in Open Government Data Platform India catalog search."""

    CATALOG_SEARCH_URL = "https://data.gov.in/api/1/datastore/search"

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def search_catalog(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search open government datasets published by Central & State departments."""
        # data.gov.in open catalog query
        encoded = urllib.parse.quote(query)
        url = f"https://data.gov.in/keywords/{encoded}"
        return [
            {
                "query": query,
                "portal": "Open Government Data Platform India (data.gov.in)",
                "catalog_url": url,
                "note": "Official portal query for national and state open datasets",
            }
        ]
