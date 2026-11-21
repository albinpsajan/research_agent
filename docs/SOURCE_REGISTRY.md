# HACKATHONIQ — OFFICIAL SOURCE REGISTRY
## Kerala, India, and Global Data Portals, Scientific Repositories, and Sensor Platforms

Authoritative catalog of official government open data portals, meteorological repositories, agricultural universities, disaster authorities, and global open Earth observation datasets registered in HackathonIQ.

---

## 1. Registry Architecture & Coverage Metrics

The **Kerala & India Official Source Registry** (`src/research/sources/kerala_india_registry.py`) provides automated source discovery, domain-to-authority matching, and targeted query generation.

### Current Registry Summary:
- **Total Official Portals Registered**: 14
- **Kerala State Authorities**: 5
- **National (India-Wide) Portals**: 5
- **Global Official Portals**: 4
- **Active / Integrated Connectors**: 11
- **Configured / Policy References**: 3

---

## 2. Kerala Official Source Catalog

| Source ID | Name & Authority | Access Type | Status | Primary Topics & Datasets | Official Base URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **KL-001** | **Kerala Open Data Portal**<br>*Kerala State IT Mission & Dept of Electronics & IT* | Catalog Search / Open Data | `INTEGRATED` | Civic metrics, demographics, department records, state registry | [data.kerala.gov.in](https://data.kerala.gov.in) |
| **KL-002** | **Department of Economics & Statistics Open Data Repository (DES ODR)**<br>*Directorate of Economics & Statistics, Govt of Kerala* | Bulk Download (CSV, XLSX, PDF) | `INTEGRATED` | Agricultural Statistics at a Glance, Land Utilization, district crop yields, rainfall statistics | [des.kerala.gov.in](https://des.kerala.gov.in) |
| **KL-003** | **KAU Agromet Advisory Bulletins**<br>*Kerala Agricultural University (KAU) & IMD Agromet* | RSS Feed / HTML / PDF | `INTEGRATED` | District-specific bi-weekly agro-meteorological advisories, pest/disease warnings across 5 agro-ecological zones | [kau.in/agromet](https://kau.in/agromet) |
| **KL-004** | **Kerala State Disaster Management Authority (KSDMA)**<br>*Dept of Revenue & Disaster Management, Govt of Kerala* | Web Portal / Spatial Layers | `INTEGRATED` | Landslide hazard susceptibility (Wayanad, Idukki), flood inundation maps (Kuttanad), dam alert levels | [ksdma.kerala.gov.in](https://ksdma.kerala.gov.in) |
| **KL-005** | **Kerala State Action Plan on Climate Change (SAPCC)**<br>*Dept of Environment and Climate Change, Govt of Kerala* | Policy Blueprint / PDF | `CONFIGURED` | Sectoral vulnerability assessments, greenhouse gas inventories, state climate adaptation priorities | [envt.kerala.gov.in](https://envt.kerala.gov.in) |

---

## 3. National (India-Wide) Official Source Catalog

| Source ID | Name & Authority | Access Type | Status | Primary Topics & Datasets | Official Base URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **IN-001** | **Open Government Data Platform India (data.gov.in)**<br>*National Informatics Centre (NIC), Ministry of Electronics & IT* | Open REST API / Catalog | `INTEGRATED` | Mandi agricultural prices (Agmarknet), rainfall anomalies, rural health, infrastructure metrics | [data.gov.in](https://data.gov.in) |
| **IN-002** | **Indian Council of Agricultural Research (ICAR)**<br>*Ministry of Agriculture & Farmers Welfare, Govt of India* | Research Repository / HTML | `CONFIGURED` | Verified crop varieties, national soil health maps, agroforestry package of practices | [icar.org.in](https://icar.org.in) |
| **IN-003** | **India Meteorological Department (IMD) Mausam & Agrimet**<br>*Ministry of Earth Sciences, Govt of India* | Open API / Gridded NetCDF | `INTEGRATED` | 0.25° x 0.25° daily gridded rainfall, Doppler radar, extreme weather nowcasts | [mausam.imd.gov.in](https://mausam.imd.gov.in) |
| **IN-004** | **ISRO Bhuvan & MOSDAC**<br>*Indian Space Research Organisation (ISRO)* | Open WMS / WFS / GeoTIFF | `INTEGRATED` | Resourcesat, Cartosat, Oceansat imagery, LULC maps, near-real-time flood inundation vectors | [bhuvan.nrsc.gov.in](https://bhuvan.nrsc.gov.in) |
| **IN-005** | **NITI Aayog Aspirational Districts & State Statistics**<br>*NITI Aayog, Government of India* | Catalog Search / CSV | `CONFIGURED` | Granular socio-economic and rural development indicators across 112 aspirational districts (including Wayanad) | [niti.gov.in](https://niti.gov.in) |

---

## 4. Global Official Dataset Catalog

| Source ID | Name & Authority | Access Type | Status | Primary Topics & Datasets | Official Base URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GL-001** | **FAOSTAT**<br>*UN Food and Agriculture Organization (FAO)* | Open REST API / CSV | `INTEGRATED` | Crop production, international agricultural trade, land cover, fertilizer use, food security | [fao.org/faostat](https://www.fao.org/faostat) |
| **GL-002** | **World Bank Open Data**<br>*The World Bank Group* | Open REST API / JSON | `INTEGRATED` | Standardized global economic indicators, rural population demographics, climate change resilience metrics | [data.worldbank.org](https://data.worldbank.org) |
| **GL-003** | **Copernicus Open Access Hub & Climate Data Store**<br>*European Space Agency (ESA) & European Commission* | Open API / SAFE / GeoTIFF | `INTEGRATED` | Sentinel-1 C-band SAR radar (all-weather monsoon penetration), Sentinel-2 optical multi-spectral, ERA5 reanalysis | [dataspace.copernicus.eu](https://dataspace.copernicus.eu) |
| **GL-004** | **NASA Earthdata (LP DAAC, SEDAC, GPM)**<br>*National Aeronautics and Space Administration (NASA)* | Open API / HDF / NetCDF | `INTEGRATED` | SRTM 30m Digital Elevation Model, GPM precipitation constellation, MODIS/VIIRS vegetation health | [earthdata.nasa.gov](https://earthdata.nasa.gov) |

---

## 5. Existing Search Connectors (Preserved)

In addition to official portals, HackathonIQ preserves 8 active open research and software connectors:
1. **GitHub API**: Open-source repository search, topic exploration, README inspection, license and star auditing.
2. **arXiv API**: Scientific preprint retrieval across computer science, machine learning, and quantitative biology.
3. **OpenAlex API**: Universal scholarly index linking millions of open scientific papers, citations, and DOI metadata.
4. **Crossref API**: Publisher-validated academic metadata, peer-reviewed citations, and author affiliations.
5. **RSS Bulletins**: Real-time research commentary feeds (MIT News, ScienceDaily, Nature News).
6. **Wikipedia API**: Broad domain ontology, terminological definition, and historical background retrieval.
7. **HackerNews Algolia**: Practitioner retrospectives, engineering discussions, and grassroots developer insights.
8. **DuckDuckGo Open Search**: General web search with strict private/hallucinated URL guards.
