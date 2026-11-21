"""Authoritative Kerala, India, and Global Official Source Registry.

Tracks official government open data portals, meteorological repositories,
agricultural universities, disaster authorities, and global open datasets.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceCoverageStatus(StrEnum):
    """Lifecycle status of a source connector or integration."""

    DISCOVERED = "discovered"
    CONFIGURED = "configured"
    INTEGRATED = "integrated"
    QUERIED = "queried"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    NOT_IMPLEMENTED = "not_implemented"


class OfficialSource(BaseModel):
    """An official governmental or scientific source in the registry."""

    id: str
    name: str
    authority: str
    geography: str  # "kerala", "india", "global"
    base_url: str
    access_type: str  # "open_api", "bulk_download", "catalog_search", "rss", "web_portal"
    status: SourceCoverageStatus = SourceCoverageStatus.CONFIGURED
    topics: list[str] = Field(default_factory=list)
    data_formats: list[str] = Field(default_factory=list)
    description: str = ""
    license: str = "Open Access / Government Open Data"


OFFICIAL_SOURCE_CATALOG: list[OfficialSource] = [
    # -------------------------------------------------------------
    # Kerala Official Sources
    # -------------------------------------------------------------
    OfficialSource(
        id="KL-001",
        name="Kerala Open Data Portal",
        authority="Kerala State IT Mission & Dept of Electronics and IT",
        geography="kerala",
        base_url="https://data.kerala.gov.in",
        access_type="catalog_search",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["governance", "demographics", "infrastructure", "agriculture", "education"],
        data_formats=["CSV", "JSON", "XML"],
        description="Official open government data portal for Kerala state departments, civic metrics, and spatial registries.",
    ),
    OfficialSource(
        id="KL-002",
        name="Department of Economics & Statistics Open Data Repository (DES ODR)",
        authority="Directorate of Economics & Statistics, Government of Kerala",
        geography="kerala",
        base_url="https://des.kerala.gov.in",
        access_type="bulk_download",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "crop_statistics", "rainfall", "economic_review", "land_utilization"],
        data_formats=["PDF", "XLSX", "CSV"],
        description="Official Kerala statistical releases: Agricultural Statistics at a Glance, Land Utilization, District-wise crop yields, and Annual Economic Reviews.",
    ),
    OfficialSource(
        id="KL-003",
        name="KAU Agromet Advisory Bulletins",
        authority="Kerala Agricultural University (KAU) & IMD Agromet",
        geography="kerala",
        base_url="https://kau.in/agromet",
        access_type="rss",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "weather_advisory", "pest_warning", "monsoon_forecast", "crop_management"],
        data_formats=["PDF", "HTML", "RSS"],
        description="District-specific bi-weekly agro-meteorological advisories tailored to Kerala's 5 agro-ecological zones with localized pest/disease warnings.",
    ),
    OfficialSource(
        id="KL-004",
        name="Kerala State Disaster Management Authority (KSDMA)",
        authority="Department of Revenue and Disaster Management, Government of Kerala",
        geography="kerala",
        base_url="https://ksdma.kerala.gov.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["landslides", "floods", "coastal_erosion", "disaster_risk", "hazard_maps"],
        data_formats=["PDF", "GeoTIFF", "HTML"],
        description="Official disaster management authority providing landslide susceptibility zones (Wayanad, Idukki), flood inundation maps (Kuttanad), and dam alert levels.",
    ),
    OfficialSource(
        id="KL-005",
        name="Kerala State Action Plan on Climate Change (SAPCC)",
        authority="Department of Environment and Climate Change, Government of Kerala",
        geography="kerala",
        base_url="https://envt.kerala.gov.in",
        access_type="web_portal",
        status=SourceCoverageStatus.CONFIGURED,
        topics=["climate_resilience", "water_resources", "biodiversity", "renewable_energy", "forests"],
        data_formats=["PDF"],
        description="State policy blueprint defining climate vulnerabilities, greenhouse gas inventories, and priority adaptation sectors across Kerala.",
    ),

    # -------------------------------------------------------------
    # National (India-Wide) Official Sources
    # -------------------------------------------------------------
    OfficialSource(
        id="IN-001",
        name="Open Government Data Platform India (data.gov.in)",
        authority="National Informatics Centre (NIC), Ministry of Electronics & IT, Government of India",
        geography="india",
        base_url="https://data.gov.in",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "market_prices", "demographics", "health", "water_resources"],
        data_formats=["JSON", "CSV", "XML"],
        description="National open data repository with APIs for agricultural market mandi prices (Agmarknet), rainfall anomalies, and rural development metrics.",
    ),
    OfficialSource(
        id="IN-002",
        name="Indian Council of Agricultural Research (ICAR)",
        authority="Department of Agricultural Research and Education, Ministry of Agriculture, Govt of India",
        geography="india",
        base_url="https://icar.org.in",
        access_type="web_portal",
        status=SourceCoverageStatus.CONFIGURED,
        topics=["crop_varieties", "soil_health", "horticulture", "agroforestry", "pest_control"],
        data_formats=["PDF", "HTML"],
        description="Premier national agricultural research body releasing verified crop varieties, soil fertility maps, and agroforestry package of practices.",
    ),
    OfficialSource(
        id="IN-003",
        name="India Meteorological Department (IMD) Mausam & Agrimet",
        authority="Ministry of Earth Sciences, Government of India",
        geography="india",
        base_url="https://mausam.imd.gov.in",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["weather", "monsoon", "rainfall_grid", "cyclones", "heatwave"],
        data_formats=["JSON", "Gridded NetCDF", "HTML"],
        description="Official national weather agency providing 0.25x0.25 degree daily gridded rainfall, high-resolution monsoon radar, and extreme weather nowcasts.",
    ),
    OfficialSource(
        id="IN-004",
        name="ISRO Bhuvan & MOSDAC",
        authority="Indian Space Research Organisation (ISRO)",
        geography="india",
        base_url="https://bhuvan.nrsc.gov.in",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["satellite_imagery", "soil_moisture", "flood_inundation", "land_use", "cartography"],
        data_formats=["WMS", "WFS", "GeoTIFF", "HDF5"],
        description="National geospatial satellite portal delivering Resourcesat, Cartosat, and Oceansat imagery, LULC maps, and real-time flood inundation vectors.",
    ),
    OfficialSource(
        id="IN-005",
        name="NITI Aayog Aspirational Districts & State Statistics",
        authority="NITI Aayog, Government of India",
        geography="india",
        base_url="https://niti.gov.in",
        access_type="catalog_search",
        status=SourceCoverageStatus.CONFIGURED,
        topics=["district_indicators", "poverty", "health", "financial_inclusion", "rural_infrastructure"],
        data_formats=["CSV", "PDF"],
        description="Granular socio-economic and rural development monitoring framework across 112 aspirational districts including Wayanad (Kerala).",
    ),

    # -------------------------------------------------------------
    # Global Official Sources
    # -------------------------------------------------------------
    OfficialSource(
        id="GL-001",
        name="FAOSTAT - UN Food and Agriculture Organization",
        authority="Food and Agriculture Organization of the United Nations (FAO)",
        geography="global",
        base_url="https://www.fao.org/faostat",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["global_agriculture", "food_security", "crop_yields", "fertilizer_use", "land_cover"],
        data_formats=["JSON", "CSV"],
        description="Global benchmark statistical database covering crop production, trade, greenhouse gas emissions, and food security indicators across 245 countries.",
    ),
    OfficialSource(
        id="GL-002",
        name="World Bank Open Data",
        authority="The World Bank Group",
        geography="global",
        base_url="https://data.worldbank.org",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["economic_indicators", "rural_population", "climate_change", "infrastructure", "poverty"],
        data_formats=["JSON", "XML", "CSV"],
        description="Standardized global socio-economic and climate resilience indicators with comprehensive open REST APIs.",
    ),
    OfficialSource(
        id="GL-003",
        name="Copernicus Open Access Hub & Climate Data Store",
        authority="European Space Agency (ESA) & European Commission",
        geography="global",
        base_url="https://dataspace.copernicus.eu",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["sentinel_satellite", "radar_sar", "land_surface_temperature", "soil_moisture", "era5_climate"],
        data_formats=["SAFE", "NetCDF", "GeoTIFF"],
        description="Global open satellite constellation: Sentinel-1 (C-band SAR radar for all-weather/cloud penetration) and Sentinel-2 (optical multi-spectral), plus ERA5 reanalysis.",
    ),
    OfficialSource(
        id="GL-004",
        name="NASA Earthdata (SEDAC, LP DAAC, MODIS/VIIRS)",
        authority="National Aeronautics and Space Administration (NASA)",
        geography="global",
        base_url="https://earthdata.nasa.gov",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["evapotranspiration", "vegetation_indices", "precipitation_gpm", "elevation_srtm"],
        data_formats=["HDF", "GeoTIFF", "NetCDF"],
        description="Global Earth observation datasets including SRTM 30m digital elevation, GPM precipitation, and MODIS vegetation health indices.",
    ),
]


class KeralaIndiaSourceRegistry:
    """Registry engine providing source discovery, recommendation, and coverage tracking."""

    def __init__(self, catalog: list[OfficialSource] | None = None) -> None:
        self.catalog = list(catalog) if catalog is not None else OFFICIAL_SOURCE_CATALOG

    def recommend_sources(
        self,
        domain_or_theme: str,
        geography: str | None = None,
        limit: int = 5,
    ) -> list[OfficialSource]:
        """Recommend official data sources matching domain keywords and geographical scope."""
        keywords = set(re.findall(r"[a-z0-9]{3,}", domain_or_theme.lower()))
        scored: list[tuple[float, OfficialSource]] = []

        for src in self.catalog:
            if geography and geography.lower() != "all" and src.geography.lower() != geography.lower():
                # Allow fallback global/india when kerala requested, but downweight
                if geography.lower() == "kerala" and src.geography.lower() in {"india", "global"}:
                    geo_weight = 0.6
                else:
                    continue
            else:
                geo_weight = 1.0

            source_tokens = set(re.findall(r"[a-z0-9]{3,}", f"{src.name} {src.description} {' '.join(src.topics)}".lower()))
            overlap = keywords & source_tokens
            score = (len(overlap) * 2.0 + (1.5 if src.status == SourceCoverageStatus.INTEGRATED else 1.0)) * geo_weight

            if score > 0:
                scored.append((score, src))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def get_coverage_summary(self) -> dict[str, Any]:
        """Produce summary metrics of registered sources across geographies and statuses."""
        by_geo: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for src in self.catalog:
            by_geo[src.geography] = by_geo.get(src.geography, 0) + 1
            by_status[src.status.value] = by_status.get(src.status.value, 0) + 1

        return {
            "total_official_sources": len(self.catalog),
            "by_geography": by_geo,
            "by_status": by_status,
        }

    def format_source_recommendations(self, sources: list[OfficialSource]) -> str:
        """Format source list for prompt injection."""
        if not sources:
            return ""
        lines = ["RECOMMENDED OFFICIAL REGIONAL & SCIENTIFIC SOURCES:"]
        for s in sources:
            lines.append(
                f"- [{s.geography.upper()}] {s.name} ({s.authority}) | URL: {s.base_url} | "
                f"Access: {s.access_type} | Topics: {', '.join(s.topics[:3])}"
            )
        return "\n".join(lines)

    def generate_targeted_queries(self, theme_or_domain: str, geography: str = "kerala") -> list[str]:
        """Generate search queries directed at official domains and regional authorities."""
        queries: list[str] = []
        if geography in {"kerala", "all"}:
            queries.extend([
                f"{theme_or_domain} site:data.kerala.gov.in OR site:des.kerala.gov.in",
                f"{theme_or_domain} site:kau.in OR site:ksdma.kerala.gov.in",
                f"Kerala {theme_or_domain} State Action Plan on Climate Change",
            ])
        if geography in {"india", "all"}:
            queries.extend([
                f"{theme_or_domain} site:data.gov.in OR site:icar.org.in",
                f"{theme_or_domain} site:mausam.imd.gov.in OR site:bhuvan.nrsc.gov.in",
            ])
        if geography in {"global", "all"}:
            queries.extend([
                f"{theme_or_domain} site:fao.org OR site:worldbank.org",
            ])
        return queries
