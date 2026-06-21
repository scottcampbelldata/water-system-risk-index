const API_BASE = ((window.APP_CONFIG && window.APP_CONFIG.apiBase) || "http://localhost:8000").replace(/\/+$/, "");

const state = {
  metadata: null,
  summary: null,
  items: [],
  total: 0,
  page: 1,
  pageSize: 100,
  points: [],
  selected: null,
  map: null,
  markerLayer: null,
  boundaryLayer: null,
  countyLayer: null,
  markerByPwsid: new Map(),
  loadToken: 0
};

const geometryTierLabels = {
  verified_service_area_boundary: "System-Sourced Service Area",
  modeled_service_area_boundary: "Modeled Service Area",
  validated_system_coordinate: "Approximate Location",
  city_or_zip_centroid: "Approximate Location",
  county_centroid: "Approximate Location",
  unmatched: "Unmatched Geography"
};

const boundaryColors = {
  verified_service_area_boundary: "#14746f",
  modeled_service_area_boundary: "#b98322"
};

const colors = {
  "Critical Review": "#8f1f1f",
  "High Review": "#a94328",
  "Moderate Review": "#b98322",
  "Monitor": "#285e8e",
  "Lower Priority": "#64748b"
};

const componentLabels = {
  compliance_risk_component: "Compliance",
  enforcement_risk_component: "Enforcement",
  vulnerability_component: "Vulnerability",
  drought_component: "Drought",
  funding_gap_component: "Funding",
  small_system_component: "Small system",
  data_quality_penalty: "Data quality"
};

const tierOrder = ["Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"];

const els = {
  metricTotal: document.getElementById("metricTotal"),
  metricHigh: document.getElementById("metricHigh"),
  metricCritical: document.getElementById("metricCritical"),
  metricValidation: document.getElementById("metricValidation"),
  geoVerified: document.getElementById("geoVerified"),
  geoModeled: document.getElementById("geoModeled"),
  geoApproximate: document.getElementById("geoApproximate"),
  geoUnmatched: document.getElementById("geoUnmatched"),
  geoSourceProtection: document.getElementById("geoSourceProtection"),
  useNotice: document.getElementById("useNotice"),
  sourceNote: document.getElementById("sourceNote"),
  searchInput: document.getElementById("searchInput"),
  countyFilter: document.getElementById("countyFilter"),
  tierFilter: document.getElementById("tierFilter"),
  sizeFilter: document.getElementById("sizeFilter"),
  geographyFilter: document.getElementById("geographyFilter"),
  showAllMarkers: document.getElementById("showAllMarkers"),
  resetFilters: document.getElementById("resetFilters"),
  tierLegend: document.getElementById("tierLegend"),
  tierChart: document.getElementById("tierChart"),
  countyChart: document.getElementById("countyChart"),
  map: document.getElementById("streetMap"),
  systemsTable: document.getElementById("systemsTable"),
  tableCount: document.getElementById("tableCount"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  pageInfo: document.getElementById("pageInfo"),
  detailSubtitle: document.getElementById("detailSubtitle"),
  systemDetail: document.getElementById("systemDetail")
};

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "--";
  return Number(value).toLocaleString();
}

function formatScore(value) {
  if (value === null || value === undefined) return "--";
  return Number(value).toFixed(2);
}

function option(label, value = label) {
  const node = document.createElement("option");
  node.textContent = label;
  node.value = value;
  return node;
}

async function api(path, params) {
  const url = new URL(API_BASE + path);
  if (params) url.search = params.toString();
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request to ${path} failed (${response.status})`);
  return response.json();
}

function filterParams() {
  const params = new URLSearchParams();
  const query = els.searchInput.value.trim();
  if (query) params.set("q", query);
  if (els.countyFilter.value) params.set("county", els.countyFilter.value);
  if (els.tierFilter.value) params.set("tier", els.tierFilter.value);
  if (els.sizeFilter.value) params.set("size", els.sizeFilter.value);
  if (els.geographyFilter.value) params.set("geography", els.geographyFilter.value);
  return params;
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function initFilters(metadata) {
  els.countyFilter.appendChild(option("All counties", ""));
  (metadata.counties || [])
    .slice()
    .sort((a, b) => a.localeCompare(b))
    .forEach(county => els.countyFilter.appendChild(option(county)));

  els.tierFilter.appendChild(option("All tiers", ""));
  tierOrder.forEach(tier => els.tierFilter.appendChild(option(tier)));

  els.sizeFilter.appendChild(option("All sizes", ""));
  ["very_small", "small", "medium", "large", "unknown"].forEach(size => els.sizeFilter.appendChild(option(size.replace("_", " "), size)));

  els.geographyFilter.appendChild(option("All geography", ""));
  [
    ["System-Sourced Service Area", "verified"],
    ["Modeled Service Area", "modeled"],
    ["Approximate Location", "approximate"],
    ["Unmatched Geography", "unmatched"]
  ].forEach(([label, value]) => els.geographyFilter.appendChild(option(label, value)));

  const onFilterChange = () => { state.page = 1; applyFilters({ resetSelection: true }); };
  els.searchInput.addEventListener("input", debounce(onFilterChange, 250));
  [els.countyFilter, els.tierFilter, els.sizeFilter, els.geographyFilter].forEach(el => {
    el.addEventListener("input", onFilterChange);
  });

  els.showAllMarkers.addEventListener("input", () => {
    renderMap();
    fitMapToFiltered();
  });

  els.resetFilters.addEventListener("click", () => {
    els.searchInput.value = "";
    els.countyFilter.value = "";
    els.tierFilter.value = "";
    els.sizeFilter.value = "";
    els.geographyFilter.value = "";
    els.showAllMarkers.checked = false;
    state.page = 1;
    applyFilters({ resetSelection: true });
  });

  els.prevPage.addEventListener("click", () => {
    if (state.page > 1) { state.page -= 1; applyFilters({ resetSelection: false }); }
  });
  els.nextPage.addEventListener("click", () => {
    if (state.page * state.pageSize < state.total) { state.page += 1; applyFilters({ resetSelection: false }); }
  });
}

async function applyFilters({ resetSelection } = { resetSelection: true }) {
  const token = ++state.loadToken;
  const base = filterParams();

  const systemsParams = new URLSearchParams(base);
  systemsParams.set("sort", "rank");
  systemsParams.set("order", "asc");
  systemsParams.set("page", String(state.page));
  systemsParams.set("page_size", String(state.pageSize));

  const [summary, systems, points] = await Promise.all([
    api("/summary", base),
    api("/systems", systemsParams),
    api("/map/points", base)
  ]);

  if (token !== state.loadToken) return; // a newer request superseded this one

  state.summary = summary;
  state.items = systems.items;
  state.total = systems.total;
  state.points = points;

  if (resetSelection || !state.selected || !state.points.some(p => p.pwsid === state.selected.pwsid)) {
    state.selected = state.items[0] || null;
  }

  render();
  fitMapToFiltered();
  // Service-area boundaries can be a few MB statewide; load them without blocking the dashboard.
  loadBoundaries(token, base);
}

function renderMetrics() {
  const summary = state.summary;
  const tierCount = tier => (summary.tiers.find(row => row.tier === tier) || { systems: 0 }).systems;
  els.metricTotal.textContent = formatNumber(summary.total);
  els.metricHigh.textContent = formatNumber(tierCount("High Review"));
  els.metricCritical.textContent = formatNumber(tierCount("Critical Review"));
  els.metricValidation.textContent = `${state.metadata.validationPassCount}/${state.metadata.validationCheckCount}`;

  const geo = summary.geography || {};
  els.geoVerified.textContent = formatNumber(geo.verifiedServiceAreas);
  els.geoModeled.textContent = formatNumber(geo.modeledServiceAreas);
  els.geoApproximate.textContent = formatNumber(geo.approximateLocations);
  els.geoUnmatched.textContent = formatNumber(geo.unmatchedGeography);
  els.geoSourceProtection.textContent = "Not loaded (Phase 1)";
}

function renderLegend() {
  els.tierLegend.innerHTML = tierOrder.map(tier => `
    <span class="legend-item"><span class="dot" style="background:${colors[tier]}"></span>${tier}</span>
  `).join("");
}

function renderBarChart(container, rows, valueKey, labelKey, colorFn) {
  const max = Math.max(1, ...rows.map(row => row[valueKey]));
  container.innerHTML = rows.map(row => {
    const width = Math.max(2, (row[valueKey] / max) * 100);
    const color = colorFn(row);
    return `
      <div class="bar-row">
        <span title="${row[labelKey]}">${row[labelKey]}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%;background:${color}"></div></div>
        <strong>${formatNumber(row[valueKey])}</strong>
      </div>
    `;
  }).join("");
}

function renderCharts() {
  const tierRows = tierOrder.map(tier => ({
    tier,
    systems: (state.summary.tiers.find(row => row.tier === tier) || { systems: 0 }).systems
  }));
  renderBarChart(els.tierChart, tierRows, "systems", "tier", row => colors[row.tier]);

  const countyRows = state.summary.topCounties;
  renderBarChart(
    els.countyChart,
    countyRows.length ? countyRows : [{ county: "No high-review records in filter", highReviewSystems: 0 }],
    "highReviewSystems",
    "county",
    () => "#14746f"
  );
}

function initializeMap() {
  const ohioBounds = L.latLngBounds([38.2, -85.2], [42.4, -80.2]);

  state.map = L.map("streetMap", {
    preferCanvas: true,
    zoomControl: true,
    scrollWheelZoom: true,
    minZoom: 7,
    maxZoom: 18,
    maxBounds: ohioBounds,
    maxBoundsViscosity: 1.0
  }).setView([40.25, -82.8], 7);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    bounds: ohioBounds,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(state.map);

  state.markerLayer = L.layerGroup().addTo(state.map);
  state.boundaryLayer = L.geoJSON(null, {
    style: feature => ({
      color: boundaryColors[feature.properties.geometrySourceTier] || "#64748b",
      weight: 1,
      fillColor: boundaryColors[feature.properties.geometrySourceTier] || "#64748b",
      fillOpacity: 0.18
    }),
    onEachFeature: (feature, layer) => {
      layer.on("click", () => selectByPwsid(feature.properties.pwsid, false));
    }
  }).addTo(state.map);
  state.countyLayer = L.geoJSON(null, {
    style: { color: "#94a3b8", weight: 1, fill: false, dashArray: "3 3" }
  });

  L.control.layers(null, {
    "Water system records": state.markerLayer,
    "Service area boundaries": state.boundaryLayer,
    "County boundaries": state.countyLayer
  }, { collapsed: false }).addTo(state.map);

  // County boundaries are a static asset, loaded once and toggled off by default.
  fetch("data/ohio_counties.geojson")
    .then(response => response.ok ? response.json() : null)
    .then(geojson => { if (geojson) state.countyLayer.addData(geojson); })
    .catch(() => {});

  setTimeout(() => state.map.invalidateSize(), 150);
  window.addEventListener("resize", () => state.map.invalidateSize());
}

async function loadBoundaries(token, base) {
  try {
    const collection = await api("/map/boundaries", base);
    if (token !== state.loadToken || !state.boundaryLayer) return;
    state.boundaryLayer.clearLayers();
    state.boundaryLayer.addData(collection);
  } catch (error) {
    // Boundaries are an enhancement layer; failure should not break the dashboard.
    if (state.boundaryLayer) state.boundaryLayer.clearLayers();
  }
}

function mapPopup(system) {
  return `
    <div class="map-popup">
      <h3>${system.name}</h3>
      <p><strong>${system.pwsid}</strong> | ${system.county}</p>
      <p>Score <strong>${formatScore(system.score)}</strong> | ${system.tier}</p>
      <p>Population ${formatNumber(system.population)} | ${geometryTierLabels[system.geometrySourceTier] || String(system.spatialConfidence || "").replace(/_/g, " ")}</p>
      <p>${(system.drivers || []).filter(Boolean).slice(0, 2).join(" + ")}</p>
    </div>
  `;
}

function markerStyle(system, selected = false) {
  const high = ["Critical Review", "High Review"].includes(system.tier);
  return {
    radius: selected ? 8 : high ? 5 : 3.5,
    color: selected ? "#17201c" : "#ffffff",
    weight: selected ? 2.5 : 1,
    fillColor: colors[system.tier] || "#64748b",
    fillOpacity: selected ? 1 : 0.78
  };
}

function markerSystems() {
  const reviewOnly = els.showAllMarkers.checked;
  return state.points.filter(system => {
    if (!Number.isFinite(system.latitude) || !Number.isFinite(system.longitude)) return false;
    if (!reviewOnly) return true;
    return ["Critical Review", "High Review", "Moderate Review"].includes(system.tier);
  });
}

function renderMap() {
  if (!state.map || !state.markerLayer) return;
  state.markerLayer.clearLayers();
  state.markerByPwsid = new Map();

  const systems = markerSystems();
  systems.forEach(system => {
    const selected = state.selected && state.selected.pwsid === system.pwsid;
    const marker = L.circleMarker([system.latitude, system.longitude], markerStyle(system, selected));
    marker.bindPopup(mapPopup(system));
    marker.on("click", () => selectByPwsid(system.pwsid, false));
    marker.addTo(state.markerLayer);
    state.markerByPwsid.set(system.pwsid, marker);
  });

  setTimeout(() => state.map.invalidateSize(), 0);
}

function fitMapToOhio() {
  if (!state.map) return;
  state.map.fitBounds([[38.25, -84.95], [42.35, -80.45]], { animate: false });
}

function fitMapToFiltered() {
  const systems = markerSystems();
  if (!state.map || systems.length === 0) {
    fitMapToOhio();
    return;
  }
  const bounds = L.latLngBounds(systems.map(system => [system.latitude, system.longitude]));
  state.map.fitBounds(bounds.pad(0.08), { maxZoom: 11, animate: false });
}

function focusSelectedOnMap(zoomToPoint = true) {
  if (!state.map || !state.selected) return;
  const marker = state.markerByPwsid.get(state.selected.pwsid);
  if (!marker) return;
  if (zoomToPoint) {
    state.map.setView(marker.getLatLng(), Math.max(state.map.getZoom(), 11), { animate: true });
  }
  marker.openPopup();
}

async function selectByPwsid(pwsid, zoom) {
  let record = state.items.find(system => system.pwsid === pwsid);
  if (!record) {
    record = await api(`/systems/${encodeURIComponent(pwsid)}`);
  }
  state.selected = record;
  renderDetail();
  renderTable();
  renderMap();
  focusSelectedOnMap(zoom);
}

function renderTable() {
  const rows = state.items;
  const start = state.total === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
  const end = Math.min(state.total, state.page * state.pageSize);
  els.tableCount.textContent = `${formatNumber(state.total)} records match filters; showing ${formatNumber(start)}-${formatNumber(end)}`;

  els.pageInfo.textContent = state.total === 0 ? "Page 0 of 0" : `Page ${state.page} of ${Math.max(1, Math.ceil(state.total / state.pageSize))}`;
  els.prevPage.disabled = state.page <= 1;
  els.nextPage.disabled = state.page * state.pageSize >= state.total;

  els.systemsTable.innerHTML = rows.map(system => `
    <tr data-pwsid="${system.pwsid}" class="${state.selected && state.selected.pwsid === system.pwsid ? "selected" : ""}">
      <td>${system.rankStatewide}</td>
      <td>${system.pwsid}</td>
      <td>${system.name}</td>
      <td>${system.county}</td>
      <td><strong>${formatScore(system.score)}</strong></td>
      <td><span class="pill" style="background:${colors[system.tier]}">${system.tier}</span></td>
      <td>${system.drivers[0]}</td>
      <td>${String(system.spatialConfidence || "").replace(/_/g, " ")}</td>
    </tr>
  `).join("");

  els.systemsTable.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", () => selectByPwsid(row.dataset.pwsid, true));
  });
}

function renderComponentBars(system) {
  return Object.entries(system.components).map(([key, value]) => `
    <div class="component-row">
      <span>${componentLabels[key]}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, value || 0))}%;background:#14746f"></div></div>
      <strong>${formatScore(value)}</strong>
    </div>
  `).join("");
}

function geographyEvidenceRow(label, value) {
  if (value === null || value === undefined || value === "") return "";
  return `<div class="evidence-row"><span>${label}</span><strong>${value}</strong></div>`;
}

function renderGeographyEvidence(system) {
  const tierLabel = geometryTierLabels[system.geometrySourceTier] || "--";
  const matched = ["verified_service_area_boundary", "modeled_service_area_boundary"].includes(system.geometrySourceTier);
  const primary = matched ? "EPA service-area polygon" : (system.geometrySourceTier === "county_centroid" ? "County centroid (approximate)" : "No geography matched");
  return `
    <div class="evidence">
      <h4>Geography evidence</h4>
      ${geographyEvidenceRow("Primary geometry", primary)}
      ${geographyEvidenceRow("Source", tierLabel)}
      ${geographyEvidenceRow("Boundary type", system.boundaryType ? system.boundaryType.replace("_", "-") : "n/a")}
      ${geographyEvidenceRow("Provider", system.boundaryProvider || "n/a")}
      ${geographyEvidenceRow("PWSID match", system.matchMethod ? system.matchMethod.replace("_", " ") : "n/a")}
      ${matched ? geographyEvidenceRow("Service area", `${formatNumber(system.areaSqKm)} km²`) : ""}
      ${geographyEvidenceRow("Spatial confidence", String(system.spatialConfidence || "").replace(/_/g, " "))}
      ${geographyEvidenceRow("Source protection", "Not evaluated (Phase 1)")}
      <p class="muted evidence-note">${system.spatialLimitationNote || ""}</p>
    </div>
  `;
}

function renderDetail() {
  const system = state.selected;
  if (!system) {
    els.detailSubtitle.textContent = "No records match the current filters.";
    els.systemDetail.innerHTML = "<p class=\"muted\">Adjust filters to restore results.</p>";
    return;
  }
  els.detailSubtitle.textContent = `${system.pwsid} | ${system.county}`;
  els.systemDetail.innerHTML = `
    <div class="detail-title">
      <div>
        <h3>${system.name}</h3>
        <p class="muted">Rank ${system.rankStatewide} statewide | Rank ${system.rankCounty} in ${system.county}</p>
      </div>
      <span class="pill" style="background:${colors[system.tier]}">${system.tier}</span>
    </div>
    <div class="fact-grid">
      <div class="fact"><span>Score</span><strong>${formatScore(system.score)}</strong></div>
      <div class="fact"><span>Population</span><strong>${formatNumber(system.population)}</strong></div>
      <div class="fact"><span>Size</span><strong>${system.sizeClass.replace("_", " ")}</strong></div>
      <div class="fact"><span>Spatial confidence</span><strong>${system.spatialConfidence}</strong></div>
      <div class="fact"><span>Violations 36m</span><strong>${formatNumber(system.violations36m)}</strong></div>
      <div class="fact"><span>Enforcement 36m</span><strong>${formatNumber(system.enforcement36m)}</strong></div>
      <div class="fact"><span>SVI percentile</span><strong>${system.svi === null ? "--" : Math.round(system.svi * 100)}</strong></div>
      <div class="fact"><span>Drought component</span><strong>${formatScore(system.components.drought_component)}</strong></div>
    </div>
    <div class="component-grid">${renderComponentBars(system)}</div>
    ${renderGeographyEvidence(system)}
    <p>${system.explanation}</p>
    <p class="muted">Funding match: ${system.fundingMatchConfidence}. ${system.fundingNotes}</p>
  `;
}

function render() {
  renderMetrics();
  renderLegend();
  renderCharts();
  renderMap();
  renderTable();
  renderDetail();
}

async function loadApp() {
  state.metadata = await api("/metadata");
  els.useNotice.textContent = state.metadata.useNote;
  els.sourceNote.textContent = state.metadata.sourceNote;

  initFilters(state.metadata);
  initializeMap();
  await applyFilters({ resetSelection: true });
  fitMapToOhio();
}

loadApp().catch(error => {
  document.body.innerHTML = `<main class="app-shell"><div class="notice">The app could not reach its data API. ${error.message}</div></main>`;
});
