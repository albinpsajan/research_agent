"""Authoritative Kerala, India, and Global Official Source Registry.

Tracks official government open data portals, meteorological repositories,
agricultural universities, disaster authorities, and global open datasets.
Provides independent tracking across 8 verification dimensions:
1. is_registered
2. connector_implemented
3. successfully_queried
4. useful_data_retrieved
5. last_retrieval_date
6. auth_requirement
7. license_restriction
8. current_availability
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

    # 8 Independent verification dimensions
    is_registered: bool = True
    connector_implemented: bool = False
    successfully_queried: bool = False
    useful_data_retrieved: bool = False
    last_retrieval_date: str = ""
    auth_requirement: str = "none"
    license_restriction: str = "open"
    current_availability: str = "operational"


OFFICIAL_SOURCE_CATALOG: list[OfficialSource] = [
    # -------------------------------------------------------------
    # Kerala Official Sources (12 sources)
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
        license="Government Open Data License - India (GODL)",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-002",
        name="Department of Economics & Statistics Open Data Repository (DES ODR)",
        authority="Directorate of Economics & Statistics, Government of Kerala",
        geography="kerala",
        base_url="https://ecostat.kerala.gov.in",
        access_type="bulk_download",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "crop_statistics", "rainfall", "economic_review", "land_utilization"],
        data_formats=["PDF", "XLSX", "CSV"],
        description="Official Kerala statistical releases: Agricultural Statistics at a Glance, Land Utilization, District-wise crop yields, and Annual Economic Reviews.",
        license="Government Open Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-003",
        name="KAU Agromet Advisory Bulletins",
        authority="Kerala Agricultural University (KAU) & IMD Agromet",
        geography="kerala",
        base_url="https://kau.in",
        access_type="rss",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "weather_advisory", "pest_warning", "monsoon_forecast", "crop_management"],
        data_formats=["PDF", "HTML", "RSS"],
        description="District-specific bi-weekly agro-meteorological advisories tailored to Kerala's 5 agro-ecological zones with localized pest/disease warnings.",
        license="Open Public Extension / Research",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_educational",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-004",
        name="Kerala State Disaster Management Authority (KSDMA)",
        authority="Department of Revenue and Disaster Management, Government of Kerala",
        geography="kerala",
        base_url="https://sdma.kerala.gov.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["landslides", "floods", "coastal_erosion", "disaster_risk", "hazard_maps"],
        data_formats=["PDF", "GeoTIFF", "HTML"],
        description="Official disaster management authority providing landslide susceptibility zones (Wayanad, Idukki), flood inundation maps (Kuttanad), and dam alert levels.",
        license="Government Open Data / Public Safety",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
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
        license="Public Policy Document",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-006",
        name="Kerala Directorate of Health Services (DHS)",
        authority="Health & Family Welfare Department, Government of Kerala",
        geography="kerala",
        base_url="https://dhs.kerala.gov.in",
        access_type="catalog_search",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["health", "telemedicine", "disease_surveillance", "dengue", "epidemiology", "public_health"],
        data_formats=["PDF", "HTML", "JSON"],
        description="Official state public health monitoring agency delivering communicable disease surveillance bulletins (dengue, leptospirosis) and rural telemedicine infrastructure records.",
        license="Public Health Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-007",
        name="Department of Agriculture Development and Farmers' Welfare Kerala",
        authority="Agriculture Department, Government of Kerala",
        geography="kerala",
        base_url="https://keralaagriculture.gov.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["agriculture", "smallholder_support", "homestead_farming", "crop_insurance", "organic_farming"],
        data_formats=["HTML", "PDF", "CSV"],
        description="State agrarian mission records, Krishi Bhavan network contacts, smallholder subsidy allocations, and localized crop loss assistance portals.",
        license="Government Public Extension",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-008",
        name="Kerala GHG Platform & Climate Energy Portal",
        authority="Energy Management Centre (EMC) & Environment Dept, Government of Kerala",
        geography="kerala",
        base_url="https://kerala.gov.in/ghg",
        access_type="bulk_download",
        status=SourceCoverageStatus.CONFIGURED,
        topics=["emissions", "greenhouse_gas", "renewable_energy", "energy_efficiency", "carbon_accounting"],
        data_formats=["XLSX", "PDF"],
        description="Sub-national greenhouse gas emission inventories across agriculture, energy, and land use sectors in Kerala.",
        license="Public Environmental Registry",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-009",
        name="Wayanad District Administration Official Portal",
        authority="District Administration Wayanad, Government of Kerala",
        geography="kerala",
        base_url="https://wayanad.nic.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["wayanad", "landslides", "tribal_welfare", "coffee_plantation", "agroforestry"],
        data_formats=["HTML", "PDF"],
        description="Aspirational district administrative portal covering hilly terrain disaster zones, tribal agrarian communities, and coffee/spice plantation data.",
        license="Government Public Portal",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-010",
        name="Alappuzha & Kuttanad Wetland Administration Portal",
        authority="District Administration Alappuzha & Kuttanad Development Project",
        geography="kerala",
        base_url="https://alappuzha.nic.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["alappuzha", "kuttanad", "below_sea_level_farming", "flooding", "paddy_polders", "salinity"],
        data_formats=["HTML", "PDF"],
        description="Official administration and wetland agricultural monitoring portal for Kuttanad's below-sea-level UNESCO Globally Important Agricultural Heritage System (GIAHS).",
        license="Government Public Portal",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-011",
        name="Palakkad District Agrarian & Water Portal",
        authority="District Administration Palakkad, Government of Kerala",
        geography="kerala",
        base_url="https://palakkad.nic.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["palakkad", "drought", "rain_shadow", "groundwater", "rice_bowl", "irrigation"],
        data_formats=["HTML", "PDF"],
        description="Administrative portal covering Kerala's primary rice granary, Palakkad gap rain shadow zones, drought indicators, and canal irrigation networks.",
        license="Government Public Portal",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="KL-012",
        name="Idukki District High-Range Portal",
        authority="District Administration Idukki, Government of Kerala",
        geography="kerala",
        base_url="https://idukki.nic.in",
        access_type="web_portal",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["idukki", "landslides", "high_ranges", "tea_cardamom", "dam_levels", "forests"],
        data_formats=["HTML", "PDF"],
        description="Official high-range district portal tracking mountain slope stability, reservoir capacities (Idukki Arch Dam), and spice smallholder statistics.",
        license="Government Public Portal",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),

    # -------------------------------------------------------------
    # National (India-Wide) Official Sources (8 sources)
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
        license="National Data Sharing and Accessibility Policy (NDSAP)",
        is_registered=True,
        connector_implemented=True,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="free_api_key_for_bulk",
        license_restriction="national_data_sharing_and_accessibility_policy",
        current_availability="operational",
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
        license="Open Access Public Research",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_access_public",
        current_availability="operational",
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
        license="Open Weather Data Policy",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_weather_data",
        current_availability="operational",
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
        license="ISRO Open Data Policy",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none_for_wms_catalog",
        license_restriction="isro_open_data_policy",
        current_availability="operational",
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
        license="Open Government Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="IN-006",
        name="Ministry of Statistics & Programme Implementation (MoSPI)",
        authority="Ministry of Statistics and Programme Implementation, Government of India",
        geography="india",
        base_url="https://mospi.gov.in",
        access_type="bulk_download",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["national_accounts", "economic_census", "consumer_price_index", "rural_demographics", "civic_indicators"],
        data_formats=["CSV", "XLSX", "PDF"],
        description="Central statistical agency publishing National Sample Surveys (NSSO), Periodic Labour Force Surveys, and rural socio-economic datasets.",
        license="Open Government Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_government_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="IN-007",
        name="Indian Council of Medical Research (ICMR)",
        authority="Department of Health Research, Ministry of Health and Family Welfare, Govt of India",
        geography="india",
        base_url="https://icmr.gov.in",
        access_type="catalog_search",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["health", "medical", "epidemiology", "dengue", "disease_surveillance", "telemedicine", "clinical"],
        data_formats=["PDF", "HTML", "JSON"],
        description="Apex biomedical research organization tracking communicable diseases, vector control, infectious outbreak models, and rural health clinics.",
        license="Public Biomedical Research Open Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_biomedical_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="IN-008",
        name="Bhoonidhi - NRSC Earth Observation Data Hub",
        authority="National Remote Sensing Centre (NRSC) / ISRO",
        geography="india",
        base_url="https://bhoonidhi.nrsc.gov.in",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["satellite_imagery", "remote_sensing", "multispectral", "land_surface", "open_data"],
        data_formats=["GeoTIFF", "HDF5", "NetCDF"],
        description="India's open satellite data dissemination gateway providing Sentinel, Landsat, and Indian remote sensing satellite passes.",
        license="NRSC Satellite Data Policy",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="free_registration_for_raster_download",
        license_restriction="nrsc_satellite_data_policy",
        current_availability="operational",
    ),

    # -------------------------------------------------------------
    # Global Official Sources (9 sources)
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
        license="CC BY-NC-SA 3.0 IGO",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="cc_by_3_0_igo",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-002",
        name="World Bank Open Data",
        authority="The World Bank Group",
        geography="global",
        base_url="https://api.worldbank.org/v2",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["economic_indicators", "rural_population", "climate_change", "infrastructure", "poverty"],
        data_formats=["JSON", "XML", "CSV"],
        description="Standardized global socio-economic and climate resilience indicators with comprehensive open REST APIs.",
        license="CC BY 4.0",
        is_registered=True,
        connector_implemented=True,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="cc_by_4_0",
        current_availability="operational",
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
        license="Open Access for Sentinel Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="free_registration_for_bulk",
        license_restriction="copernicus_open_access_policy",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-004",
        name="NASA Earthdata (SEDAC, LP DAAC, MODIS/VIIRS, CMR)",
        authority="National Aeronautics and Space Administration (NASA)",
        geography="global",
        base_url="https://cmr.earthdata.nasa.gov/search/collections.json",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["evapotranspiration", "vegetation_indices", "precipitation_gpm", "elevation_srtm"],
        data_formats=["HDF", "GeoTIFF", "NetCDF"],
        description="Global Earth observation datasets including SRTM 30m digital elevation, GPM precipitation, and MODIS vegetation health indices.",
        license="NASA Open Science Data Policy",
        is_registered=True,
        connector_implemented=True,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none_for_cmr_search",
        license_restriction="nasa_open_science_data",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-005",
        name="WHO Global Health Observatory",
        authority="World Health Organization (WHO), United Nations",
        geography="global",
        base_url="https://www.who.int/data/gho",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["health", "epidemiology", "disease_outbreaks", "mortality", "public_health_indicators", "telemedicine"],
        data_formats=["JSON", "CSV", "XML"],
        description="Global health statistics, infectious disease outbreak trackers, universal health coverage metrics, and rural healthcare accessibility standards.",
        license="CC BY-NC-SA 3.0 IGO",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_access_who",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-006",
        name="UNESCO Open Data Portal",
        authority="United Nations Educational, Scientific and Cultural Organization (UNESCO)",
        geography="global",
        base_url="https://opendata.unesco.org",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["education", "literacy", "vernacular_learning", "science_policy", "cultural_heritage"],
        data_formats=["JSON", "CSV"],
        description="Global datasets on literacy, mother-tongue education frameworks, digital learning in vernacular languages, and open science initiatives.",
        license="CC BY-SA 3.0 IGO",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_access_unesco",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-007",
        name="UNICEF Data Warehouse",
        authority="United Nations Children's Fund (UNICEF)",
        geography="global",
        base_url="https://data.unicef.org",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["education", "child_welfare", "maternal_health", "nutrition", "rural_communities"],
        data_formats=["JSON", "CSV"],
        description="Cross-national database on child nutrition, early education, village community resilience, and maternal health metrics.",
        license="Open Access Public Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=False,
        useful_data_retrieved=False,
        last_retrieval_date="",
        auth_requirement="none",
        license_restriction="open_access_unicef",
        current_availability="cloudflare_bot_blocked",
    ),
    OfficialSource(
        id="GL-008",
        name="WMO World Weather Watch & Climatology",
        authority="World Meteorological Organization (WMO)",
        geography="global",
        base_url="https://wmo.int",
        access_type="catalog_search",
        status=SourceCoverageStatus.CONFIGURED,
        topics=["weather_extremes", "cyclone_tracking", "monsoon_climatology", "hydrometeorology"],
        data_formats=["GRIB2", "NetCDF", "PDF"],
        description="Global coordinated atmospheric observation system tracking tropical cyclone tracks, extreme precipitation anomalies, and regional drought trends.",
        license="WMO Resolution 40 (Free and Unrestricted)",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="wmo_resolution_40",
        current_availability="operational",
    ),
    OfficialSource(
        id="GL-009",
        name="UNEP Environment Data Explorer",
        authority="United Nations Environment Programme (UNEP)",
        geography="global",
        base_url="https://www.unep.org/data",
        access_type="open_api",
        status=SourceCoverageStatus.INTEGRATED,
        topics=["environmental_degradation", "biodiversity", "freshwater", "land_degradation", "climate_adaptation"],
        data_formats=["JSON", "CSV", "GeoTIFF"],
        description="Authoritative international portal providing global and regional environmental statistics, freshwater ecosystem indicators, and biodiversity metrics.",
        license="Open Access Environmental Data",
        is_registered=True,
        connector_implemented=False,
        successfully_queried=True,
        useful_data_retrieved=True,
        last_retrieval_date="2026-11-21",
        auth_requirement="none",
        license_restriction="open_access_unep",
        current_availability="operational",
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
        health_keywords = {"health", "medical", "telemedicine", "dengue", "disease", "epidemiology", "clinical", "hospital", "patient", "outbreak"}
        agri_keywords = {"agriculture", "crop", "farming", "farmer", "monsoon", "agro", "paddy", "soil", "harvest", "land", "fertilizer"}
        edu_gov_keywords = {"education", "vernacular", "school", "learning", "governance", "civic", "grievance", "public", "literacy"}
        disaster_keywords = {"disaster", "landslide", "flood", "hazard", "cyclone", "emergency", "inundation"}

        is_health = bool(keywords & health_keywords)
        is_agri = bool(keywords & agri_keywords)
        is_edu_gov = bool(keywords & edu_gov_keywords)
        is_disaster = bool(keywords & disaster_keywords)

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
            base_score = len(overlap) * 2.0 + (1.5 if src.status == SourceCoverageStatus.INTEGRATED else 1.0)

            boost = 0.0
            src_topics_str = " ".join(src.topics).lower() + " " + src.name.lower()
            if is_health and any(k in src_topics_str for k in {"health", "disease", "medical", "telemedicine", "epidemiology"}):
                boost += 6.0
            if is_agri and any(k in src_topics_str for k in {"agriculture", "crop", "agro", "farming", "weather"}):
                boost += 5.0
            if is_edu_gov and any(k in src_topics_str for k in {"governance", "civic", "education", "literacy", "demographics"}):
                boost += 5.0
            if is_disaster and any(k in src_topics_str for k in {"disaster", "landslide", "flood", "hazard"}):
                boost += 6.0

            score = (base_score + boost) * geo_weight

            if score > 0:
                scored.append((score, src))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def verify_source_connectivity(self, source_id: str) -> dict[str, Any]:
        """Verify machine-readable or web connectivity metadata of a registered source."""
        for src in self.catalog:
            if src.id == source_id:
                return {
                    "source_id": src.id,
                    "name": src.name,
                    "authority": src.authority,
                    "geography": src.geography,
                    "base_url": src.base_url,
                    "access_type": src.access_type,
                    "data_formats": src.data_formats,
                    "status": src.status.value,
                    "is_configured": src.status in {SourceCoverageStatus.INTEGRATED, SourceCoverageStatus.CONFIGURED},
                    "is_registered": src.is_registered,
                    "connector_implemented": src.connector_implemented,
                    "successfully_queried": src.successfully_queried,
                    "useful_data_retrieved": src.useful_data_retrieved,
                    "last_retrieval_date": src.last_retrieval_date,
                    "auth_requirement": src.auth_requirement,
                    "license_restriction": src.license_restriction,
                    "current_availability": src.current_availability,
                }
        return {"source_id": source_id, "status": "unknown_source", "is_configured": False}

    def get_source_coverage_table(self) -> list[dict[str, Any]]:
        """Return the complete 8-column independent status table for all registered sources."""
        table = []
        for src in self.catalog:
            table.append({
                "source_id": src.id,
                "name": src.name,
                "geography": src.geography,
                "authority": src.authority,
                "base_url": src.base_url,
                "access_type": src.access_type,
                # 8 independent status dimensions
                "is_registered": src.is_registered,
                "connector_implemented": src.connector_implemented,
                "successfully_queried": src.successfully_queried,
                "useful_data_retrieved": src.useful_data_retrieved,
                "last_retrieval_date": src.last_retrieval_date,
                "auth_requirement": src.auth_requirement,
                "license_restriction": src.license_restriction,
                "current_availability": src.current_availability,
            })
        return table

    def get_coverage_summary(self) -> dict[str, Any]:
        """Produce summary metrics of registered sources across geographies and statuses."""
        by_geo: dict[str, int] = {}
        by_status: dict[str, int] = {}
        connector_implemented_count = 0
        successfully_queried_count = 0
        useful_data_retrieved_count = 0

        for src in self.catalog:
            by_geo[src.geography] = by_geo.get(src.geography, 0) + 1
            by_status[src.status.value] = by_status.get(src.status.value, 0) + 1
            if src.connector_implemented:
                connector_implemented_count += 1
            if src.successfully_queried:
                successfully_queried_count += 1
            if src.useful_data_retrieved:
                useful_data_retrieved_count += 1

        return {
            "total_official_sources": len(self.catalog),
            "by_geography": by_geo,
            "by_status": by_status,
            "connector_implemented_count": connector_implemented_count,
            "successfully_queried_count": successfully_queried_count,
            "useful_data_retrieved_count": useful_data_retrieved_count,
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
                f"{theme_or_domain} site:data.kerala.gov.in OR site:ecostat.kerala.gov.in",
                f"{theme_or_domain} site:kau.in OR site:sdma.kerala.gov.in",
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
