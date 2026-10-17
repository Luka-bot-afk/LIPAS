# LIPAS qualitative comparison framework

Ordinal labels only. They are not converted to numbers and are not summed.

Compact forms in Table 2: VH = Very High, H = High, M = Moderate, L = Low, VL = Very Low, N = None.

Systems compared: LIPAS, DONKI, Diviner, LDEX, Apollo PSE, MEM 3, GOES-18 primary products.

## Criteria and scoring rules

### Hazard coverage
- N = no hazard addressed
- VL = one hazard type only
- L = up to two hazards
- M = three to four hazards
- H = five hazards
- VH = six or more hazards in one system

### Data fusion
- N = single dataset only
- L = multiple datasets with no shared pipeline
- M = partial integration of multiple sources
- H = integrated multi-source system
- VH = live multi-source fusion into one forecast path

### Temporal forecasting
- N = archival only
- L = event alerts with no forward horizon
- M = short-range estimate for a narrow domain
- H = multi-day forecast for one or more hazards
- VH = multi-day forecast across all listed hazards together

### Spatial coverage
- N = no spatial product
- VL = historical sites only
- L = one region or polar area
- M = broad regional coverage
- H = global or near-global coverage of the relevant environment
- VH = selectable lunar coordinates across the mapped surface

### Real-time operations
- N = mission ended or historical only
- L = archival access with long lag
- M = near-real-time with limited refresh
- H = live feeds with regular updates
- VH = continuous ingest with automated processing

### Robustness and stability
- L = limited coverage or known gaps
- M = usable but dependent on external APIs and public feeds
- H = stable within a narrow validated domain
- VH = long-running calibrated mission instruments

### Validation strength
- N = no comparison to observations
- L = informal or sparse comparison
- M = structured comparison for a limited period (often proxies)
- H = peer-reviewed validation against direct measurements
- VH = direct physical measurement by design

### Usability and readiness
- VL = raw products for specialists only
- L = technical interfaces for trained users
- M = API or portal that still needs specialist knowledge
- H = clear interface for operational reading
- VH = interactive dashboard aimed at mission planning use

### Openness and accessibility
- L = registration or processing barriers
- M = partial public access
- H = open API or published data products
- VH = browser access without local setup for the interface itself

## Assigned Table 2 scores (basis)

| System | Hazard | Fusion | Forecast | Spatial | Real-time | Robust. | Valid. | Usability | Open | Basis |
|--------|--------|--------|----------|---------|-----------|---------|--------|-----------|------|-------|
| LIPAS | VH | VH | H | H | H | M | M | VH | H | Six hazards in one hybrid stack and dashboard; public feeds; validation still proxy-limited |
| DONKI | L | L | L | M | H | H | H | M | H | Event catalog and APIs for heliophysics alerts ([NASA DONKI](https://api.nasa.gov/DONKI/)) |
| Diviner | VL | L | L | VH | L | VH | VH | L | M | LRO Diviner surface temperature products ([Paige et al. 2010](https://doi.org/10.1007/s11214-009-9529-2); [Williams et al. 2017](https://doi.org/10.1016/j.icarus.2016.08.012)) |
| LDEX | VL | L | N | L | N | M | H | VL | M | LADEE dust experiment archive ([Horanyi et al. 2015](https://doi.org/10.1038/nature14479)) |
| Apollo PSE | VL | L | N | VL | N | H | VH | L | H | Apollo seismic catalogs ([Nakamura 2005](https://doi.org/10.1029/2004JE002332); [Nunn et al. 2020](https://doi.org/10.1007/s11214-020-00709-3)) |
| MEM 3 | VL | L | M | H | L | H | H | L | M | Meteoroid engineering model ([Moorhead et al. 2020](https://ntrs.nasa.gov/citations/20200001093)) |
| GOES-18 | L | M | M | M | VH | VH | VH | M | H | Operational X-ray and proton space-weather streams ([NOAA SWPC](https://services.swpc.noaa.gov/)) |

## What the qualitative result means

LIPAS scores high on coverage, fusion, and usability because it joins six hazards and public feeds in one planner-facing interface. It scores only Moderate on robustness and validation because it depends on public APIs and many targets are proxies rather than continuous surface truth.

Agency products score high on validation and robustness inside their own domain (Diviner temperature, GOES protons, Apollo seismicity, MEM 3 engineering flux) but score low on multi-hazard coverage and planner-facing fusion. The table is comparative context for RQ2, not a claim that LIPAS is safer or more accurate than those specialized systems.

In plain terms: the qualitative matrix supports building one consultative dashboard, not replacing Diviner, GOES, MEM 3, or Apollo catalogs. High usability does not repair Moderate validation. That is why the locked RMSE windows, not this table, answer RQ3.

## References used for the comparison

- NASA DONKI API documentation: https://api.nasa.gov/DONKI/
- NOAA SWPC data services: https://services.swpc.noaa.gov/
- Paige et al. (2010), Space Science Reviews, Diviner experiment
- Williams et al. (2017), Icarus, Diviner global temperatures
- Horanyi et al. (2015), Nature, lunar dust cloud / LDEX
- Nakamura (2005), JGR Planets, deep moonquakes
- Nunn et al. (2020), Space Science Reviews, lunar seismology review
- Moorhead et al. (2020), NASA MEM 3 technical report
- Spence et al. (2010), Space Science Reviews, CRaTER
- Schwadron et al. (2014), Space Weather, CRaTER radiation environment
- OMNI / King & Papitashvili (2005), JGR, solar-wind data scales
- Camporeale (2019), Space Weather, ML in space weather (method context)
