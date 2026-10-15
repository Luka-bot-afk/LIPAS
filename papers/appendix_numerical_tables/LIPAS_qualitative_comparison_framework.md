# LIPAS Qualitative Comparison Framework

Classification rules for each criterion (ordinal labels only; not summed).  
Full wording: None, Very Low, Low, Moderate, High, Very High.  
In Table 2 of the manuscript the compact forms are: VH = Very High, H = High, M = Moderate, L = Low, VL = Very Low, N = None.

## Hazard Coverage
- **None** = no hazard addressed
- **Very Low** = one hazard type only
- **Low** = up to two hazards
- **Moderate** = three to four hazards
- **High** = five hazards
- **Very High** = six or more hazards integrated

## Data Fusion Capability
- **None** = single dataset only
- **Low** = multiple datasets with no integration
- **Moderate** = partial integration of multiple sources
- **High** = integrated multi-source system
- **Very High** = real-time dynamic multi-source fusion

## Temporal Forecasting Ability
- **None** = no forecasting, archival only
- **Low** = event-driven alerts, no time horizon
- **Moderate** = short-range estimates for a narrow domain
- **High** = multi-day forecasting for one or more hazards
- **Very High** = multi-day forecasting across all hazards simultaneously

## Spatial Coverage
- **None** = no spatial resolution
- **Very Low** = limited to specific historical measurement sites
- **Low** = single region or polar area only
- **Moderate** = broad regional coverage
- **High** = global or near-global coverage of relevant environments
- **Very High** = complete global lunar surface coverage with location selection

## Real-time Operational Capability
- **None** = mission ended or historical only
- **Low** = archival access with significant delay
- **Moderate** = near-real-time with limited update frequency
- **High** = live data feeds with regular updates
- **Very High** = continuous real-time data with automated processing

## Robustness and Stability
- **Low** = limited coverage or known gaps
- **Moderate** = functional with notable dependencies on external APIs or data sources
- **High** = well-validated and operationally stable within a narrow domain
- **Very High** = continuously calibrated mission-grade instruments with long operational history

## Validation Strength
- **None** = no comparison against observed data
- **Low** = informal or limited comparison
- **Moderate** = structured comparison against observed data for a limited period
- **High** = peer-reviewed validation against direct measurements
- **Very High** = direct physical measurement, self-validating by design

## Usability and Operational Readiness
- **Very Low** = raw scientific data only, requires specialist processing
- **Low** = accessible via technical interfaces for trained users
- **Moderate** = accessible via API or web portal with some technical knowledge
- **High** = clear interface for operational use
- **Very High** = interactive dashboard designed for non-specialist mission planners

## Openness and Accessibility
- **Low** = registration or processing barriers
- **Moderate** = partial public access
- **High** = open API or published data products
- **Very High** = fully open browser-based access without setup

These rules produce the scores in manuscript Table 2. Categories are not converted into numbers or summed into a single total score.
