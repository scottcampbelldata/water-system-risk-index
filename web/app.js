const state = {
  data: null,
  filtered: [],
  selected: null,
  map: null,
  markerLayer: null,
  markerByPwsid: new Map()
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
  metricSpatial: document.getElementById("metricSpatial"),
  metricValidation: document.getElementById("metricValidation"),
  useNotice: document.getElementById("useNotice"),
  sourceNote: document.getElementById("sourceNote"),
  searchInput: document.getElementById("searchInput"),
  countyFilter: document.getElementById("countyFilter"),
  tierFilter: document.getElementById("tierFilter"),
  sizeFilter: document.getElementById("sizeFilter"),
  spatialFilter: document.getElementById("spatialFilter"),
  showAllMarkers: document.getElementById("showAllMarkers"),
  resetFilters: document.getElementById("resetFilters"),
  tierLegend: document.getElementById("tierLegend"),
  tierChart: document.getElementById("tierChart"),
  countyChart: document.getElementById("countyChart"),
  map: document.getElementById("streetMap"),
  systemsTable: document.getElementById("systemsTable"),
  tableCount: document.getElementById("tableCount"),
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

function initFilters(data) {
  els.countyFilter.appendChild(option("All counties", ""));
  data.counties
    .map(d => d.county)
    .sort((a, b) => a.localeCompare(b))
    .forEach(county => els.countyFilter.appendChild(option(county)));

  els.tierFilter.appendChild(option("All tiers", ""));
  tierOrder.forEach(tier => els.tierFilter.appendChild(option(tier)));

  els.sizeFilter.appendChild(option("All sizes", ""));
  ["very_small", "small", "medium", "large", "unknown"].forEach(size => els.sizeFilter.appendChild(option(size.replace("_", " "), size)));

  els.spatialFilter.appendChild(option("All spatial confidence", ""));
  ["high", "medium", "low", "unknown"].forEach(value => els.spatialFilter.appendChild(option(value)));

  [els.searchInput, els.countyFilter, els.tierFilter, els.sizeFilter, els.spatialFilter, els.showAllMarkers].forEach(el => {
    el.addEventListener("input", applyFilters);
  });

  els.resetFilters.addEventListener("click", () => {
    els.searchInput.value = "";
    els.countyFilter.value = "";
    els.tierFilter.value = "";
    els.sizeFilter.value = "";
    els.spatialFilter.value = "";
    els.showAllMarkers.checked = false;
    applyFilters();
  });
}

function applyFilters() {
  const query = els.searchInput.value.trim().toLowerCase();
  const county = els.countyFilter.value;
  const tier = els.tierFilter.value;
  const size = els.sizeFilter.value;
  const spatial = els.spatialFilter.value;

  state.filtered = state.data.systems.filter(system => {
    const haystack = `${system.pwsid} ${system.name} ${system.county}`.toLowerCase();
    return (!query || haystack.includes(query))
      && (!county || system.county === county)
      && (!tier || system.tier === tier)
      && (!size || system.sizeClass === size)
      && (!spatial || system.spatialConfidence === spatial);
  });

  if (!state.filtered.includes(state.selected)) {
    state.selected = state.filtered[0] || null;
  }

  render();
  fitMapToFiltered();
}

function renderMetrics() {
  const systems = state.filtered;
  els.metricTotal.textContent = formatNumber(systems.length);
  els.metricHigh.textContent = formatNumber(systems.filter(d => d.tier === "High Review").length);
  els.metricCritical.textContent = formatNumber(systems.filter(d => d.tier === "Critical Review").length);
  els.metricSpatial.textContent = formatNumber(systems.filter(d => ["low", "unknown"].includes(d.spatialConfidence)).length);
  els.metricValidation.textContent = `${state.data.metadata.validationPassCount}/${state.data.metadata.validationCheckCount}`;
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
    systems: state.filtered.filter(d => d.tier === tier).length
  }));
  renderBarChart(els.tierChart, tierRows, "systems", "tier", row => colors[row.tier]);

  const byCounty = new Map();
  state.filtered.forEach(system => {
    if (!byCounty.has(system.county)) byCounty.set(system.county, { county: system.county, highReviewSystems: 0 });
    if (["Critical Review", "High Review"].includes(system.tier)) {
      byCounty.get(system.county).highReviewSystems += 1;
    }
  });
  const countyRows = [...byCounty.values()]
    .sort((a, b) => b.highReviewSystems - a.highReviewSystems || a.county.localeCompare(b.county))
    .slice(0, 12)
    .filter(row => row.highReviewSystems > 0);
  renderBarChart(els.countyChart, countyRows.length ? countyRows : [{ county: "No high-review systems in filter", highReviewSystems: 0 }], "highReviewSystems", "county", () => "#14746f");
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
  setTimeout(() => state.map.invalidateSize(), 150);
  window.addEventListener("resize", () => state.map.invalidateSize());
}

function mapPopup(system) {
  return `
    <div class="map-popup">
      <h3>${system.name}</h3>
      <p><strong>${system.pwsid}</strong> | ${system.county}</p>
      <p>Score <strong>${formatScore(system.score)}</strong> | ${system.tier}</p>
      <p>Population ${formatNumber(system.population)} | Spatial ${system.spatialConfidence}</p>
      <p>${system.drivers.slice(0, 2).join(" + ")}</p>
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
  return state.filtered.filter(system => {
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
    marker.on("click", () => {
      state.selected = system;
      renderDetail();
      renderTable();
      renderMap();
      focusSelectedOnMap(false);
    });
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

function renderTable() {
  const rows = state.filtered.slice().sort((a, b) => a.rankStatewide - b.rankStatewide).slice(0, 100);
  els.tableCount.textContent = `${formatNumber(state.filtered.length)} systems match filters; showing top ${rows.length}`;
  els.systemsTable.innerHTML = rows.map(system => `
    <tr data-pwsid="${system.pwsid}" class="${state.selected && state.selected.pwsid === system.pwsid ? "selected" : ""}">
      <td>${system.rankStatewide}</td>
      <td>${system.pwsid}</td>
      <td>${system.name}</td>
      <td>${system.county}</td>
      <td><strong>${formatScore(system.score)}</strong></td>
      <td><span class="pill" style="background:${colors[system.tier]}">${system.tier}</span></td>
      <td>${system.drivers[0]}</td>
      <td>${system.spatialConfidence}</td>
    </tr>
  `).join("");

  els.systemsTable.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", () => {
      state.selected = state.filtered.find(system => system.pwsid === row.dataset.pwsid);
      renderDetail();
      renderTable();
      renderMap();
      focusSelectedOnMap(true);
    });
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

function renderDetail() {
  const system = state.selected;
  if (!system) {
    els.detailSubtitle.textContent = "No systems match the current filters.";
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
  const response = await fetch("data/app_data.json?v=street-map-1");
  if (!response.ok) throw new Error("Unable to load app_data.json");
  state.data = await response.json();
  state.filtered = state.data.systems;
  state.selected = state.data.systems.slice().sort((a, b) => a.rankStatewide - b.rankStatewide)[0];

  els.useNotice.textContent = state.data.metadata.useNote;
  els.sourceNote.textContent = state.data.metadata.sourceNote;

  initFilters(state.data);
  initializeMap();
  render();
  fitMapToOhio();
}

loadApp().catch(error => {
  document.body.innerHTML = `<main class="app-shell"><div class="notice">The app could not load its data file. ${error.message}</div></main>`;
});
