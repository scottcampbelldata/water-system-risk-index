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
  swapLayer: null,
  countyLayer: null,
  markerByPwsid: new Map(),
  loadToken: 0,
  loading: false
};

// Incremented on each selectByPwsid call so a slow /systems/{pwsid} fetch from an
// earlier click cannot overwrite the detail panel for a later one.
let selectToken = 0;

const geometryTierLabels = {
  verified_service_area_boundary: "System-Sourced Service Area",
  modeled_service_area_boundary: "Modeled Service Area",
  validated_system_coordinate: "Approximate Location",
  city_or_zip_centroid: "Approximate Location",
  county_centroid: "Approximate Location",
  unmatched: "Unmatched Geography"
};

// Overlay colours live in styles.css alongside the rest of the palette, so they
// follow the theme instead of sitting at one fixed value on both grounds.
const boundaryVar = {
  verified_service_area_boundary: "--ov-verified",
  modeled_service_area_boundary: "--ov-modeled"
};

const swapVar = {
  groundwater_swpa: "--ov-groundwater",       // 5-year groundwater protection area
  inner_management_zone: "--ov-inner-zone",   // 1-year inner management zone
  surface_water_inland: "--ov-surface",       // surface-water protection area (watershed)
  surface_water_lake_erie: "--ov-surface",
  surface_water_ohio_river: "--ov-surface"
};

function boundaryColor(tier) {
  return cssVar(boundaryVar[tier] || "--ov-fallback", "#5a5f58");
}

function swapColor(kind) {
  return cssVar(swapVar[kind] || "--ov-fallback", "#5a5f58");
}

// Three legend categories for the SWAP overlay (surface-water types share a colour).
function swapLegendRows() {
  return [
    [swapColor("groundwater_swpa"), "Groundwater protection area"],
    [swapColor("inner_management_zone"), "Inner management zone"],
    [swapColor("surface_water_inland"), "Surface-water protection area"]
  ];
}

const swapKindLabels = {
  groundwater_swpa: "Groundwater protection area",
  inner_management_zone: "Inner management zone",
  surface_water_inland: "Surface water (inland)",
  surface_water_lake_erie: "Surface water (Lake Erie)",
  surface_water_ohio_river: "Surface water (Ohio River)"
};

function prettyKinds(value) {
  if (!value) return "";
  return value.split("|").map(k => swapKindLabels[k] || k.replace(/_/g, " ")).join(", ");
}

// The review ramp lives in styles.css so a single source governs both the sheet
// and the map, and so a theme change moves both together. It is monotonic in
// lightness, which is what lets the tier survive greyscale.
const tierVar = {
  "Critical Review": "--tier-critical",
  "High Review": "--tier-high",
  "Moderate Review": "--tier-moderate",
  "Monitor": "--tier-monitor",
  "Lower Priority": "--tier-lower"
};

function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function tierColor(tier) {
  return cssVar(tierVar[tier] || "--ink-3", "#5a5f58");
}

function tierSlug(tier) {
  return String(tier).toLowerCase().replace(/\s+/g, "-");
}

// State is a mark, not a hue: five notches filled to the tier's step, so the
// ranking reads correctly in greyscale, under colour-blindness, and in print.
function tierMark(tier) {
  const step = tierOrder.length - tierOrder.indexOf(tier);
  let notches = "";
  for (let i = 1; i <= tierOrder.length; i += 1) {
    notches += i <= step ? '<i class="on"></i>' : "<i></i>";
  }
  return `<span class="tier-mark" data-tier="${tierSlug(tier)}">` +
    `<span class="tier-ramp" aria-hidden="true">${notches}</span>` +
    `<span class="tier-name">${esc(tier)}</span></span>`;
}

const componentLabels = {
  compliance_risk_component: "Compliance",
  enforcement_risk_component: "Enforcement",
  vulnerability_component: "Vulnerability",
  drought_component: "Drought",
  funding_gap_component: "Funding",
  small_system_component: "Small system",
  data_quality_penalty: "Data quality"
};

// Published weights, shown beside each component so a score can be read back to
// what produced it rather than taken on trust.
const componentWeights = {
  compliance_risk_component: "30% weight",
  enforcement_risk_component: "15% weight",
  vulnerability_component: "20% weight",
  drought_component: "10% weight",
  funding_gap_component: "15% weight",
  small_system_component: "10% weight",
  data_quality_penalty: "-5% weight"
};

const tierOrder = ["Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"];

const els = {
  metricTotal: document.getElementById("metricTotal"),
  metricHigh: document.getElementById("metricHigh"),
  metricCritical: document.getElementById("metricCritical"),
  metricValidation: document.getElementById("metricValidation"),
  ledgerModerate: document.getElementById("ledgerModerate"),
  ledgerApprox: document.getElementById("ledgerApprox"),
  findingCluster: document.getElementById("findingCluster"),
  noteApprox: document.getElementById("noteApprox"),
  noteTotal: document.getElementById("noteTotal"),
  editionLine: document.getElementById("editionLine"),
  geoVerified: document.getElementById("geoVerified"),
  geoModeled: document.getElementById("geoModeled"),
  geoApproximate: document.getElementById("geoApproximate"),
  geoUnmatched: document.getElementById("geoUnmatched"),
  geoSourceProtection: document.getElementById("geoSourceProtection"),
  useNotice: document.getElementById("useNotice"),
  errorBanner: document.getElementById("errorBanner"),
  appShell: document.querySelector("main.app-shell"),
  sourceNote: document.getElementById("sourceNote"),
  searchInput: document.getElementById("searchInput"),
  countyFilter: document.getElementById("countyFilter"),
  tierFilter: document.getElementById("tierFilter"),
  sizeFilter: document.getElementById("sizeFilter"),
  geographyFilter: document.getElementById("geographyFilter"),
  showAllMarkers: document.getElementById("showAllMarkers"),
  resetFilters: document.getElementById("resetFilters"),
  themeControl: document.getElementById("themeControl"),
  tierLegend: document.getElementById("tierLegend"),
  overlayLegend: document.getElementById("overlayLegend"),
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

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "--";
  return Number(value).toLocaleString();
}

function formatDate(iso) {
  if (!iso) return "";
  const parts = String(iso).split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return String(iso);
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "long", day: "numeric", timeZone: "UTC"
  }).format(date);
}

// API enums arrive as snake_case. The table already unslugged some of them and
// the record did not, so "medium_high" was rendering raw beside "very small".
// Compound modifiers take a hyphen; everything else takes a space. "medium_high"
// is one adjective, "very_small" is two words.
const enumLabels = {
  medium_high: "Medium-high",
  medium_low: "Medium-low",
  very_small: "Very small",
  very_large: "Very large"
};

function humanize(value) {
  if (value === null || value === undefined || value === "") return "--";
  const key = String(value).trim();
  if (enumLabels[key]) return enumLabels[key];
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Components are 0-100 model outputs. Two decimals implied a precision the
// model does not have, and rendered 100.00 as a wall of digits.
function formatComponent(value) {
  if (value === null || value === undefined) return "--";
  return Number(value).toFixed(1).replace(/\.0$/, "");
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

function showErrorBanner(message) {
  if (!els.errorBanner) return;
  els.errorBanner.textContent = message;
  els.errorBanner.hidden = false;
}

function clearErrorBanner() {
  if (!els.errorBanner) return;
  els.errorBanner.hidden = true;
  els.errorBanner.textContent = "";
}

function setLoading(isLoading) {
  state.loading = isLoading;
  if (els.appShell) {
    els.appShell.setAttribute("aria-busy", isLoading ? "true" : "false");
    // One authored moment: the whole field settles together, so a single filter
    // change reads as one linked update, not four independent refreshes.
    els.appShell.dataset.updating = isLoading ? "true" : "false";
  }
  if (isLoading && els.systemsTable && !els.systemsTable.children.length) {
    els.systemsTable.innerHTML = `<tr class="table-status"><td colspan="8">Loading…</td></tr>`;
  }
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
  ["very_small", "small", "medium", "large", "unknown"].forEach(size => els.sizeFilter.appendChild(option(size.replace(/_/g, " "), size)));

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

  setLoading(true);
  let summary, systems;
  try {
    [summary, systems] = await Promise.all([
      api("/summary", base),
      api("/systems", systemsParams)
    ]);
  } catch (error) {
    if (token !== state.loadToken) return; // a newer request superseded this one
    setLoading(false);
    // Non-fatal: keep prior state and surface an inline banner instead of the fatal handler.
    showErrorBanner(`Could not refresh the data. ${error.message}. Adjust a filter or reload the page to try again.`);
    if (els.systemsTable) {
      els.systemsTable.querySelectorAll("tr.table-status").forEach(row => row.remove());
    }
    render();
    return;
  }

  if (token !== state.loadToken) return; // a newer request superseded this one

  clearErrorBanner();
  state.summary = summary;
  state.items = systems.items;
  state.total = systems.total;

  if (resetSelection || !state.selected) {
    state.selected = state.items[0] || null;
  }

  render();
  setLoading(false);
  // The map point set is several megabytes. It loads after the page is usable, so
  // a headline figure never waits on map geometry.
  loadPoints(token, base);
  // Service-area boundaries can be a few MB statewide; load them without blocking the dashboard.
  loadBoundaries(token, base);
  loadSwap(token, base); // no-op unless the user has enabled the SWAP overlay
}

// /metadata is 5 KB and already carries every headline figure. Painting from it
// puts the finding on screen in about half a second instead of after the map
// payload lands. /summary later overwrites these with filter-aware counts.
function renderMetadataFigures() {
  const m = state.metadata;
  if (!m) return;
  els.metricTotal.textContent = formatNumber(m.systemCount);
  els.metricHigh.textContent = formatNumber(m.highReviewCount);
  els.metricCritical.textContent = formatNumber(m.criticalReviewCount);
  els.metricValidation.textContent = `${m.validationPassCount} of ${m.validationCheckCount}`;

  if (els.editionLine) {
    els.editionLine.textContent =
      `${m.state} / Model ${m.modelVersion} / Scored ${formatDate(m.scoreDate)}`;
  }
  if (els.findingCluster) {
    els.findingCluster.textContent = m.criticalReviewCount === 0
      ? "None reach Critical Review."
      : `${formatNumber(m.criticalReviewCount)} reach Critical Review.`;
  }

  const geo = m.geographyBreakdown || {};
  els.geoVerified.textContent = formatNumber(geo.verifiedServiceAreas);
  els.geoModeled.textContent = formatNumber(geo.modeledServiceAreas);
  els.geoApproximate.textContent = formatNumber(geo.approximateLocations);
  els.geoUnmatched.textContent = formatNumber(geo.unmatchedGeography);
  els.geoSourceProtection.textContent = geo.sourceProtectionAvailable === undefined
    ? "not loaded"
    : formatNumber(geo.sourceProtectionAvailable);
  if (els.noteApprox) els.noteApprox.textContent = formatNumber(geo.approximateLocations);
  if (els.noteTotal) els.noteTotal.textContent = formatNumber(m.systemCount);
  if (els.ledgerApprox) els.ledgerApprox.textContent = formatNumber(geo.approximateLocations);

  renderGeographyComposition(geo, m.systemCount);
}

function renderMetrics() {
  const summary = state.summary;
  const tierCount = tier => (summary.tiers.find(row => row.tier === tier) || { systems: 0 }).systems;
  const high = tierCount("High Review");
  const critical = tierCount("Critical Review");

  els.metricTotal.textContent = formatNumber(summary.total);
  els.metricHigh.textContent = formatNumber(high);
  if (els.ledgerModerate) els.ledgerModerate.textContent = formatNumber(tierCount("Moderate Review"));
  els.metricCritical.textContent = formatNumber(critical);
  els.metricValidation.textContent =
    `${state.metadata.validationPassCount} of ${state.metadata.validationCheckCount}`;

  if (els.editionLine) {
    els.editionLine.textContent =
      `${state.metadata.state} / Model ${state.metadata.modelVersion} / Scored ${formatDate(state.metadata.scoreDate)}`;
  }

  // The second line of the finding is computed from the current summary, never
  // asserted. It states only what these counts can support.
  if (els.findingCluster) {
    const counties = (summary.topCounties || []).filter(row => row.highReviewSystems > 0);
    const held = counties.reduce((sum, row) => sum + row.highReviewSystems, 0);
    const sentences = [];
    sentences.push(critical === 0
      ? "None reach Critical Review."
      : `${formatNumber(critical)} reach Critical Review.`);
    if (counties.length > 1 && high > 0) {
      sentences.push(
        `The ${counties.length} counties charted below hold ${formatNumber(held)} of them, ` +
        `and ${counties[0].county} County leads with ${formatNumber(counties[0].highReviewSystems)}.`
      );
    }
    els.findingCluster.textContent = sentences.join(" ");

    // The plate's accessible name carries a live figure, not a baked-in one.
    const host = document.getElementById("heroMap");
    if (host && counties.length) {
      host.setAttribute("aria-label",
        `Map of Ohio's 88 counties shaded by average review-priority score, with counties ` +
        `holding high-review systems marked. ${counties[0].county} County leads with ` +
        `${counties[0].highReviewSystems}. Exact county figures are in the ranked county list below.`);
    }
  }

  const geo = summary.geography || {};
  els.geoVerified.textContent = formatNumber(geo.verifiedServiceAreas);
  els.geoModeled.textContent = formatNumber(geo.modeledServiceAreas);
  els.geoApproximate.textContent = formatNumber(geo.approximateLocations);
  els.geoUnmatched.textContent = formatNumber(geo.unmatchedGeography);
  els.geoSourceProtection.textContent = geo.sourceProtectionAvailable === undefined
    ? "not loaded"
    : formatNumber(geo.sourceProtectionAvailable);

  // The limitation is stated with this run's own numbers rather than numbers
  // baked into the markup, so it cannot drift out of step with the data.
  if (els.noteApprox) els.noteApprox.textContent = formatNumber(geo.approximateLocations);
  if (els.ledgerApprox) els.ledgerApprox.textContent = formatNumber(geo.approximateLocations);

  renderGeographyComposition(geo, summary.total);
  if (els.noteTotal) els.noteTotal.textContent = formatNumber(summary.total);
}

// The geometry caveat is the model's biggest one, so it gets shown rather than
// only stated. Same composition-bar language the weights use.
function renderGeographyComposition(geo, total) {
  const bar = document.getElementById("geoBar");
  const key = document.getElementById("geoKey");
  if (!bar || !key) return;

  const rows = [
    ["System-sourced service area", geo.verifiedServiceAreas, 6],
    ["Modelled service area", geo.modeledServiceAreas, 4],
    ["Approximate location", geo.approximateLocations, 2],
    ["Unmatched", geo.unmatchedGeography, 0]
  ].filter(row => Number(row[1]) > 0);

  if (!rows.length || !total) { bar.hidden = true; key.hidden = true; return; }
  bar.hidden = false;
  key.hidden = false;

  bar.innerHTML = rows.map(([, count, step]) =>
    `<i style="flex:${count}" data-step="${step}"></i>`).join("");

  key.innerHTML = rows.map(([label, count, step]) =>
    `<li><i class="weight-key" data-step="${step}" aria-hidden="true"></i>` +
    `<span>${esc(label)}</span> <b>${formatNumber(count)}</b></li>`).join("");
}

function renderLegend() {
  els.tierLegend.innerHTML = tierOrder.map(tier => `
    <span class="legend-item"><span class="dot" style="background:${tierColor(tier)}"></span>${tier}</span>
  `).join("");
}

function legendBlock(title, items) {
  return `<div class="overlay-legend-group"><span class="overlay-legend-title">${title}</span>` +
    items.map(([color, label]) => `<span class="legend-item"><span class="swatch" style="background:${color}"></span>${label}</span>`).join("") +
    `</div>`;
}

// Explains the polygon overlays currently shown on the map. The marker tier legend
// (Critical/High/etc.) is separate; this covers boundary and source-protection colors.
function renderOverlayLegend() {
  if (!els.overlayLegend || !state.map) return;
  const sections = [];
  if (state.boundaryLayer && state.map.hasLayer(state.boundaryLayer)) {
    sections.push(legendBlock("Service area boundaries", [
      [boundaryColor("verified_service_area_boundary"), "System-sourced"],
      [boundaryColor("modeled_service_area_boundary"), "Modeled"]
    ]));
  }
  if (state.swapLayer && state.map.hasLayer(state.swapLayer)) {
    sections.push(legendBlock("Source-water protection areas (where supply is protected)", swapLegendRows()));
  }
  els.overlayLegend.innerHTML = sections.join("");
  els.overlayLegend.hidden = sections.length === 0;
}

function renderBarChart(container, rows, valueKey, labelKey, colorFn) {
  const max = Math.max(1, ...rows.map(row => row[valueKey]));
  container.innerHTML = rows.map(row => {
    // A zero count draws no bar. A minimum-width floor on an empty tier reads
    // as a small non-zero value, which is a lie the eye believes before the figure.
    const value = row[valueKey] || 0;
    const width = value > 0 ? Math.max(1.2, (value / max) * 100) : 0;
    const color = colorFn(row);
    return `
      <div class="bar-row">
        <span title="${esc(row[labelKey])}">${esc(row[labelKey])}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%;background:${color}"></div></div>
        <strong class="bar-value">${formatNumber(row[valueKey])}</strong>
      </div>
    `;
  }).join("");
}

function renderCharts() {
  const tierRows = tierOrder.map(tier => ({
    tier,
    systems: ((state.summary.tiers || []).find(row => row.tier === tier) || { systems: 0 }).systems
  }));
  const anyTier = tierRows.some(row => row.systems > 0);
  if (!anyTier) {
    els.tierChart.innerHTML = `<p class="muted chart-empty">No systems match these filters.</p>`;
  } else {
    renderBarChart(els.tierChart, tierRows, "systems", "tier", row => tierColor(row.tier));
  }

  const countyRows = state.summary.topCounties || [];
  renderBarChart(
    els.countyChart,
    countyRows.length ? countyRows : [{ county: "No high-review records in filter", highReviewSystems: 0 }],
    "highReviewSystems",
    "county",
    () => "var(--tier-high)"
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
      color: boundaryColor(feature.properties.geometrySourceTier),
      weight: 1,
      fillColor: boundaryColor(feature.properties.geometrySourceTier),
      fillOpacity: 0.18
    }),
    onEachFeature: (feature, layer) => {
      layer.on("click", () => selectByPwsid(feature.properties.pwsid, false));
    }
  }).addTo(state.map);
  // Source-water protection areas (where supply is protected) - distinct from
  // service-area boundaries. Off by default and loaded on demand.
  state.swapLayer = L.geoJSON(null, {
    style: feature => ({
      color: swapColor(feature.properties.areaKind),
      weight: 1,
      dashArray: "4 3",
      fillColor: swapColor(feature.properties.areaKind),
      fillOpacity: 0.14
    }),
    onEachFeature: (feature, layer) => {
      layer.bindPopup(`<div class="map-popup"><h3>${esc(feature.properties.name || feature.properties.pwsid)}</h3>` +
        `<p><strong>${esc(feature.properties.pwsid)}</strong></p>` +
        `<p>${esc(swapKindLabels[feature.properties.areaKind] || feature.properties.areaKind)}</p>` +
        `<p class="muted">Source-water protection area - where the supply is protected, not a service area.</p></div>`);
    }
  });

  state.countyLayer = L.geoJSON(null, {
    style: () => ({ color: cssVar("--ov-county", "#8a8f88"), weight: 1, fill: false, dashArray: "3 3" })
  });

  L.control.layers(null, {
    "Water system records": state.markerLayer,
    "Service area boundaries": state.boundaryLayer,
    "Source water protection areas": state.swapLayer,
    "County boundaries": state.countyLayer
  }, { collapsed: true }).addTo(state.map);

  // The SWAP overlay is several MB statewide; fetch only when the user enables it.
  state.map.on("overlayadd", event => {
    if (event.layer === state.swapLayer) loadSwap(state.loadToken, filterParams());
    renderOverlayLegend();
  });
  state.map.on("overlayremove", event => {
    if (event.layer === state.swapLayer) state.swapLayer.clearLayers();
    renderOverlayLegend();
  });
  // Refetch the active overlays for the new viewport when the map pans/zooms.
  state.map.on("moveend", debounce(() => {
    const base = filterParams();
    loadBoundaries(state.loadToken, base);
    loadSwap(state.loadToken, base);
  }, 350));
  renderOverlayLegend();

  // County boundaries are a static asset, loaded once and toggled off by default.
  fetch("data/ohio_counties.geojson")
    .then(response => response.ok ? response.json() : null)
    .then(geojson => { if (geojson) state.countyLayer.addData(geojson); })
    .catch(() => {});

  setTimeout(() => state.map.invalidateSize(), 150);
  window.addEventListener("resize", () => state.map.invalidateSize());
}

// Append the current map viewport as a bbox so only visible polygons are fetched.
function withBbox(base) {
  const params = new URLSearchParams(base);
  if (state.map) {
    const b = state.map.getBounds();
    params.set("bbox", [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(n => n.toFixed(4)).join(","));
  }
  return params;
}

async function loadPoints(token, base) {
  try {
    const points = await api("/map/points", base);
    if (token !== state.loadToken) return; // a newer request superseded this one
    state.points = points;
    renderMap();
    fitMapToFiltered();
  } catch (error) {
    if (token !== state.loadToken) return;
    showErrorBanner(`Could not load the map points. ${error.message}. The ranked list below is unaffected.`);
  }
}

async function loadBoundaries(token, base) {
  if (!state.boundaryLayer || !state.map.hasLayer(state.boundaryLayer)) return;
  try {
    const collection = await api("/map/boundaries", withBbox(base));
    if (token !== state.loadToken || !state.map.hasLayer(state.boundaryLayer)) return;
    state.boundaryLayer.clearLayers();
    state.boundaryLayer.addData(collection);
  } catch (error) {
    // Boundaries are an enhancement layer; failure should not break the dashboard.
    if (state.boundaryLayer) state.boundaryLayer.clearLayers();
  }
}

async function loadSwap(token, base) {
  if (!state.swapLayer || !state.map.hasLayer(state.swapLayer)) return;
  try {
    const collection = await api("/map/swap", withBbox(base));
    if (token !== state.loadToken || !state.map.hasLayer(state.swapLayer)) return;
    state.swapLayer.clearLayers();
    state.swapLayer.addData(collection);
  } catch (error) {
    if (state.swapLayer) state.swapLayer.clearLayers();
  }
}

function mapPopup(system) {
  return `
    <div class="map-popup">
      <h3>${esc(system.name)}</h3>
      <p><strong>${esc(system.pwsid)}</strong> | ${esc(system.county)}</p>
      <p>Score <strong>${formatScore(system.score)}</strong> | ${esc(system.tier)}</p>
      <p>Population ${formatNumber(system.population)} | ${esc(geometryTierLabels[system.geometrySourceTier] || String(system.spatialConfidence || "").replace(/_/g, " "))}</p>
      <p>${esc((system.drivers || []).filter(Boolean).slice(0, 2).join(" + "))}</p>
    </div>
  `;
}

function markerStyle(system, selected = false) {
  const high = ["Critical Review", "High Review"].includes(system.tier);
  return {
    radius: selected ? 8 : high ? 5 : 3.5,
    color: selected ? cssVar("--ink", "#0c0c0b") : cssVar("--paper", "#fbfbf9"),
    weight: selected ? 2.5 : 1,
    fillColor: tierColor(system.tier),
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
    const animate = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    state.map.setView(marker.getLatLng(), Math.max(state.map.getZoom(), 11), { animate });
  }
  marker.openPopup();
}

async function selectByPwsid(pwsid, zoom) {
  const myToken = ++selectToken;
  let record = state.items.find(system => system.pwsid === pwsid);
  if (!record) {
    try {
      record = await api(`/systems/${encodeURIComponent(pwsid)}`);
    } catch (error) {
      if (myToken !== selectToken) return;
      console.error(`Could not load system ${pwsid}:`, error);
      els.errorBanner.textContent = "This system's details could not be loaded. Choose it again to retry.";
      els.errorBanner.hidden = false;
      return;
    }
    if (myToken !== selectToken) return; // a newer selection superseded this one
  }
  clearErrorBanner();
  state.selected = record;
  renderDetail();
  renderTable();
  renderMap();
  focusSelectedOnMap(zoom);
  // Rendering the table replaces its buttons. Move focus to the new detail
  // content so keyboard users retain their place and phone users see the result.
  const detailPanel = document.getElementById("system-detail");
  detailPanel.focus({ preventScroll: true });
  detailPanel.scrollIntoView({ block: "start", behavior: "instant" });
}

function renderTable() {
  const rows = state.items;
  const start = state.total === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
  const end = Math.min(state.total, state.page * state.pageSize);
  els.tableCount.textContent = `${formatNumber(state.total)} records match filters; showing ${formatNumber(start)}-${formatNumber(end)}`;

  els.pageInfo.textContent = state.total === 0 ? "Page 0 of 0" : `Page ${state.page} of ${Math.max(1, Math.ceil(state.total / state.pageSize))}`;
  els.prevPage.disabled = state.page <= 1;
  els.nextPage.disabled = state.page * state.pageSize >= state.total;

  if (!rows.length) {
    els.systemsTable.innerHTML = `<tr class="table-status"><td colspan="8">No systems match these filters.</td></tr>`;
    return;
  }

  els.systemsTable.innerHTML = rows.map(system => `
    <tr class="${state.selected && state.selected.pwsid === system.pwsid ? "selected" : ""}">
      <td class="rank">${esc(system.rankStatewide)}</td>
      <td class="code" translate="no">${esc(system.pwsid)}</td>
      <td><button type="button" class="system-link" data-pwsid="${esc(system.pwsid)}" aria-controls="system-detail">${esc(system.name)}</button></td>
      <td>${esc(system.county)}</td>
      <td class="num">${formatScore(system.score)}</td>
      <td>${tierMark(system.tier)}</td>
      <td>${esc((system.drivers?.[0]) ?? "")}</td>
      <td>${esc(humanize(system.spatialConfidence))}</td>
    </tr>
  `).join("");

  els.systemsTable.querySelectorAll("button[data-pwsid]").forEach(button => {
    button.addEventListener("click", () => selectByPwsid(button.dataset.pwsid, true));
  });
}

function renderComponentBars(system) {
  return Object.entries(system.components ?? {}).map(([key, value]) => `
    <div class="component-row">
      <span>${esc(componentLabels[key] || key)}<br><span class="component-weight">${esc(componentWeights[key] || "")}</span></span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, value || 0))}%"></div></div>
      <strong class="bar-value">${formatComponent(value)}</strong>
    </div>
  `).join("");
}

function geographyEvidenceRow(label, value) {
  if (value === null || value === undefined || value === "") return "";
  return `<div class="evidence-row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
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
      ${geographyEvidenceRow("Boundary type", system.boundaryType ? system.boundaryType.replace(/_/g, "-") : "n/a")}
      ${geographyEvidenceRow("Provider", system.boundaryProvider || "n/a")}
      ${geographyEvidenceRow("PWSID match", system.matchMethod ? system.matchMethod.replace(/_/g, " ") : "n/a")}
      ${matched ? geographyEvidenceRow("Service area", `${formatNumber(system.areaSqKm)} km²`) : ""}
      ${geographyEvidenceRow("Geometry confidence", humanize(system.spatialConfidence))}
      ${geographyEvidenceRow("Source protection", system.sourceProtectionStatus === "available" ? `Available - ${prettyKinds(system.sourceProtectionKinds)}` : "None found")}
      <p class="muted evidence-note">${esc(system.spatialLimitationNote || "")}</p>
    </div>
  `;
}

function renderDetail() {
  const system = state.selected;
  if (!system) {
    els.detailSubtitle.textContent = "No records match the current filters.";
    els.systemDetail.innerHTML = "<p class=\"funding-note\">Adjust the filters to restore results.</p>";
    return;
  }
  els.detailSubtitle.textContent = `${system.pwsid} | ${system.county}`;
  els.systemDetail.innerHTML = `
    <div class="detail-title">
      <div>
        <h3>${esc(system.name)}</h3>
        <p>Rank ${esc(system.rankStatewide)} statewide. Rank ${esc(system.rankCounty)} in ${esc(system.county)}.</p>
      </div>
      ${tierMark(system.tier)}
    </div>
    <div class="fact-grid">
      <div class="fact"><span>Score</span><strong>${formatScore(system.score)}</strong></div>
      <div class="fact"><span>Population</span><strong>${formatNumber(system.population)}</strong></div>
      <div class="fact"><span>Size</span><strong>${esc(humanize(system.sizeClass))}</strong></div>
      <div class="fact"><span>Geometry confidence</span><strong>${esc(humanize(system.spatialConfidence))}</strong></div>
      <div class="fact"><span>Violations 36m</span><strong>${formatNumber(system.violations36m)}</strong></div>
      <div class="fact"><span>Enforcement 36m</span><strong>${formatNumber(system.enforcement36m)}</strong></div>
      <div class="fact"><span>SVI percentile</span><strong>${system.svi === null ? "--" : Math.round(system.svi * 100)}</strong></div>
      <div class="fact"><span>Drought</span><strong>${formatComponent(system.components?.drought_component)}</strong></div>
    </div>
    <div class="component-grid">${renderComponentBars(system)}</div>
    ${renderGeographyEvidence(system)}
    <p class="explanation">${esc(system.explanation)}</p>
    <p class="funding-note">Funding match: ${esc(system.fundingMatchConfidence)}. ${esc(system.fundingNotes)}</p>
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


// ---------------------------------------------------------------- hero plate
// The opening map is drawn from web/data/ohio_counties.geojson (65 KB, bundled)
// rather than from the API, so the page's focal point is on screen immediately
// and never waits on the multi-megabyte point set.

const HERO_STEPS = 6;

function mercatorY(lat) {
  // Scaled to degrees so it shares units with longitude on the x axis; without
  // the conversion the state renders about a tenth of its true height.
  // Negated so that increasing latitude moves up the SVG.
  return -(180 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
}

function heroScaleFor(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  // Quantile breaks: an equal-interval scale on this distribution leaves the
  // top two bands almost empty and the map reads as one flat colour.
  const breaks = [];
  for (let i = 1; i < HERO_STEPS; i += 1) {
    breaks.push(sorted[Math.floor((i / HERO_STEPS) * sorted.length)]);
  }
  return value => {
    let step = 0;
    while (step < breaks.length && value >= breaks[step]) step += 1;
    return step + 1;
  };
}

async function renderHeroMap() {
  const host = document.getElementById("heroMap");
  if (!host) return;

  let geo;
  try {
    const response = await fetch("data/ohio_counties.geojson");
    if (!response.ok) throw new Error(`status ${response.status}`);
    geo = await response.json();
  } catch (error) {
    host.remove(); // the finding still reads without its plate
    return;
  }

  const features = (geo.features || []).filter(f => f.geometry && f.geometry.coordinates);
  if (!features.length) { host.remove(); return; }

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  features.forEach(f => f.geometry.coordinates.forEach(ring => ring.forEach(([lon, lat]) => {
    const y = mercatorY(lat);
    if (lon < minX) minX = lon;
    if (lon > maxX) maxX = lon;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  })));

  const W = 620;
  const H = Math.round(W * ((maxY - minY) / (maxX - minX)));
  const px = lon => ((lon - minX) / (maxX - minX)) * W;
  const py = lat => ((mercatorY(lat) - minY) / (maxY - minY)) * H;

  const stepOf = heroScaleFor(features.map(f => f.properties.avg_score || 0));
  const maxHigh = Math.max(1, ...features.map(f => f.properties.high_review_count || 0));

  const paths = [];
  const marks = [];
  features.forEach((f, i) => {
    const p = f.properties || {};
    const step = stepOf(p.avg_score || 0);
    const high = p.high_review_count || 0;
    const d = f.geometry.coordinates
      .map(ring => "M" + ring.map(([lon, lat]) => `${px(lon).toFixed(1)} ${py(lat).toFixed(1)}`).join("L") + "Z")
      .join("");
    const name = String(p.county_name || "").replace(/ County$/, "");
    paths.push(
      `<path class="county${high > 0 ? " is-hot" : ""}" d="${d}" fill="var(--c${step})" style="--i:${i}"` +
      ` data-name="${esc(name)}" data-high="${high}" data-systems="${p.system_count || 0}"` +
      ` data-score="${(p.avg_score || 0).toFixed(1)}"><title>${esc(name)}: ${high} high review</title></path>`
    );
    if (high > 0) {
      // Centroid of the outer ring is close enough at state scale.
      const ring = f.geometry.coordinates[0];
      let sx = 0, sy = 0;
      ring.forEach(([lon, lat]) => { sx += px(lon); sy += py(lat); });
      const r = 1.6 + 4.4 * Math.sqrt(high / maxHigh);
      marks.push(`<circle class="county-mark" cx="${(sx / ring.length).toFixed(1)}" cy="${(sy / ring.length).toFixed(1)}" r="${r.toFixed(1)}"/>`);
    }
  });

  host.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" focusable="false">` +
    `<g>${paths.join("")}</g><g>${marks.join("")}</g></svg>`;

  const scale = document.getElementById("heroScale");
  if (scale) {
    let cells = "";
    for (let i = 1; i <= HERO_STEPS; i += 1) cells += `<i style="background:var(--c${i})"></i>`;
    scale.innerHTML = cells;
  }

  const readout = document.getElementById("heroReadout");
  if (readout) {
    const show = event => {
      const el = event.target.closest(".county");
      if (!el) return;
      const high = Number(el.dataset.high);
      readout.textContent =
        `${el.dataset.name}: ${formatNumber(el.dataset.systems)} systems, ` +
        `${high} high review, mean score ${el.dataset.score}`;
    };
    host.addEventListener("pointermove", show);
    host.addEventListener("pointerleave", () => { readout.textContent = ""; });
  }
}

async function loadApp() {
  state.metadata = await api("/metadata");
  els.useNotice.textContent = state.metadata.useNote;
  els.useNotice.hidden = false;
  els.sourceNote.textContent = state.metadata.sourceNote;

  renderMetadataFigures();
  initFilters(state.metadata);
  initializeMap();
  await applyFilters({ resetSelection: true });
  fitMapToOhio();
}

// Theme control: System / Light / Dark, persisted in localStorage. The pre-paint
// attribute is set by theme.js; this wires the segmented control and keeps the
// pressed state in sync. "system" clears the attribute so prefers-color-scheme
// governs. Set up before loadApp so the toggle works even if the API is down.
// Everything whose colour JavaScript wrote rather than CSS: legend swatches,
// index bars, map markers and the vector overlays.
function repaintThemedGraphics() {
  if (state.summary) { renderLegend(); renderCharts(); }
  if (!state.map) return;
  renderMap();
  [state.boundaryLayer, state.swapLayer, state.countyLayer].forEach(layer => {
    if (layer && layer.setStyle) layer.setStyle(layer.options.style);
  });
  renderOverlayLegend();
}

function setupTheme() {
  const control = els.themeControl;
  if (!control) return;
  const buttons = Array.from(control.querySelectorAll("[data-theme-choice]"));
  let stored = null;
  try { stored = localStorage.getItem("theme"); } catch (e) { stored = null; }
  let current = stored === "light" || stored === "dark" ? stored : "system";

  const sync = () => buttons.forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.themeChoice === current)));

  const apply = choice => {
    current = choice;
    if (choice === "light" || choice === "dark") {
      document.documentElement.setAttribute("data-theme", choice);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    try { localStorage.setItem("theme", choice); } catch (e) { /* private mode */ }
    sync();
    // The ramp is read back from CSS, so a theme change has to repaint anything
    // JavaScript coloured: legend swatches, index bars and map markers.
    repaintThemedGraphics();
  };

  buttons.forEach(b => b.addEventListener("click", () => apply(b.dataset.themeChoice)));

  // In Auto the OS can change the theme with no click to hang repainting off.
  // CSS follows on its own; anything JavaScript coloured has to be told.
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystemChange = () => {
    if (current !== "system") return;
    repaintThemedGraphics();
  };
  if (media.addEventListener) media.addEventListener("change", onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);

  sync();
}

setupTheme();

// The plate depends on nothing but a bundled file, so it paints before the first
// API response rather than after it.
renderHeroMap();

// Keep anchor targets and focused details clear of the responsive sticky header.
const stickyHeader = document.querySelector(".masthead");
const updateHeaderHeight = () => document.documentElement.style.setProperty(
  "--sticky-header-height", `${stickyHeader.getBoundingClientRect().height}px`
);
updateHeaderHeight();
new ResizeObserver(updateHeaderHeight).observe(stickyHeader);

// The map container is flex-sized inside the survey band, so Leaflet has to be
// told when the grid settles on a height.
const mapHost = document.getElementById("streetMap");
if (mapHost && "ResizeObserver" in window) {
  let mapResizeFrame = 0;
  new ResizeObserver(() => {
    cancelAnimationFrame(mapResizeFrame);
    mapResizeFrame = requestAnimationFrame(() => {
      if (state.map) state.map.invalidateSize({ animate: false });
    });
  }).observe(mapHost);
}

loadApp().catch(error => {
  // Keep the shell. The masthead, the hero plate (which loads from a bundled
  // file and is unaffected), the method notes and the colophon all still stand
  // on their own; replacing the body threw away a working page.
  showErrorBanner(
    `The data API could not be reached. ${error.message}. ` +
    `The map and figures below need it; reload to try again.`
  );
  document.querySelectorAll(".settles").forEach(el => { el.dataset.stale = "true"; });
  if (els.appShell) els.appShell.setAttribute("aria-busy", "false");
});
