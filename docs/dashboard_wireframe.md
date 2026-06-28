# Power BI Dashboard Wireframe

> **Status (historical):** This is the original Power BI wireframe. The project
> ultimately shipped an interactive **web** dashboard (Leaflet + FastAPI) instead of
> a Power BI report; the Power BI-ready exports in `data/powerbi/` remain available
> for anyone who prefers to build the report below. See the [README](../README.md)
> and [`web/`](../web/) for the live implementation.

## Page 1: Executive Summary

- Total records (Ohio public water system records)
- High Review systems
- Critical Review systems
- Population served by High/Critical Review systems
- Systems with low or unknown spatial confidence
- Top counties by review-priority systems
- Ranked top 25 systems
- Screening model disclaimer

## Page 2: Statewide Map

- Systems or service areas colored by risk tier
- Filters: county, system size, owner type, water source, risk tier, spatial confidence
- Tooltip: score, population served, top drivers, spatial confidence

## Page 3: Compliance and Enforcement

- Violations by year
- Violation category bar chart
- Repeat violation table
- Compliance risk versus enforcement risk scatterplot

## Page 4: Funding Gap

- High-review systems with no matched recent SRF funding record
- Funding by county
- Match confidence slicer
- Warning that unmatched funding may reflect matching limitations

## Page 5: Vulnerability and Drought

- Risk versus SVI scatterplot
- Drought exposure by county
- High-vulnerability systems table

## Page 6: System Detail

- Drill-through by PWSID
- System profile
- Risk score and component bars
- Compliance, enforcement, funding, geography confidence
- Explanation text

## Page 7: Methodology and Limitations

- Scoring weights
- Data sources and refresh dates
- Model version
- Known limitations
- Appropriate and inappropriate uses
