# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences land on the same URL, in this order:

1. **Evaluating reviewer** (primary for the public surface). A hiring manager, principal
   data scientist, or consulting lead following a resume or LinkedIn link. Desktop or
   laptop, roughly 40 seconds of attention, no domain briefing, no intent to operate
   filters. They need to learn what was found, judge whether the method is defensible,
   and conclude that the author can ship production work.
2. **Domain reviewer**. A state SRF/DWSRF analyst, Ohio EPA staffer, planner, grant
   writer, or infrastructure consultant who genuinely wants to screen systems. They
   arrive knowing the vocabulary (PWSID, SDWA, health-based violation, SVI) and want to
   filter, sort, look up a named system, and read its evidence.

The page must serve audience 1 first and hand off to audience 2 without a second page.

## Product Purpose

Rank every public drinking water system in Ohio by how much it warrants earlier human
review for compliance support, technical assistance, infrastructure funding research, or
resilience planning. Success is a reviewer trusting the ranking enough to act on the top
of the list, and understanding precisely why each system sits where it does.

It is explicitly **not** a regulatory finding, legal determination, engineering siting
tool, or a claim that any system is unsafe. That constraint is load-bearing and must
survive any redesign.

## Positioning

Explainability is the mechanism. Every score decomposes into seven weighted components
whose weights live in version-controlled config, and every record carries its own
geometry provenance and a plain-language explanation of its ranking. A neighboring
product could publish a risk score; it could not truthfully claim that each score is
reproducible from public data, decomposable on screen, and shipped with its own
uncertainty attached.

The second, rarer commitment: the model reports what it cannot support. Unmatched
funding records are stated as unmatched rather than as absence of funding, and
low-confidence geography is labeled as such at the record level.

## Operating Context

- Prototype state is Ohio; the pipeline is organized so more states can be added.
- Scores are batch-computed and served read-only. There is no login, no write path, and
  no per-user state beyond a theme preference.
- The public surface is a static bundle on Cloudflare Pages
  (`water-risk.scottcampbell.io`) reading a FastAPI backend
  (`water-api.scottcampbell.io`) that does server-side filtering, sorting, and paging.
- The evaluating reviewer will very likely arrive from a link in a hiring context and
  may never scroll past the first screen.

## Capabilities and Constraints

Confirmed functionality:

- 16,339 scored Ohio system records, one row per PWSID.
- Score 0–100 from seven components: compliance 30%, enforcement 15%, vulnerability 20%,
  drought 10%, funding gap 15%, small-system context 10%, data-quality penalty −5%.
- Five review tiers: Critical Review, High Review, Moderate Review, Monitor, Lower Priority.
- Statewide Leaflet map with system markers, service-area boundary polygons, and
  source-water protection area overlays.
- Filters: free-text search (PWSID / name / county), county, tier, size class, geography
  confidence. Server-side paging at 100 rows.
- Per-system detail: rank statewide and in county, population, size class, violations and
  enforcement over 36 months, SVI percentile, drought component, per-component bars,
  geography evidence block, plain-language explanation, funding-match note.
- Light / dark / system theme, persisted to localStorage, applied pre-paint.

Technical constraints that bind any redesign:

- Vanilla HTML, CSS, and JS. No build step, no framework, no bundler. Leaflet is vendored
  locally.
- Content-Security-Policy is `script-src 'self'` — no inline `<script>`. Any pre-paint
  work stays in an external file (`theme.js`).
- All rendering happens through `app.js` innerHTML templates keyed to specific element
  IDs and class names. Markup contracts to preserve: `#metricTotal`, `#metricHigh`,
  `#metricCritical`, `#metricValidation`, the `geo*` IDs, `#tierChart`, `#countyChart`,
  `#systemsTable`, `#systemDetail`, `#streetMap`, `#tierLegend`, `#overlayLegend`, the
  filter and pager IDs, and the `.bar-row` / `.bar-track` / `.bar-fill` / `.pill` /
  `.fact` / `.component-row` / `.evidence-row` class families.

Undecided: whether additional states ship, and whether SRF project-level funding data is
ever staged for Ohio.

## Brand Commitments

- Name: **Water System Risk & Funding Priority Index**.
- The disclaimer language ("review-priority screening model, not a regulatory finding…")
  is served from the API as `useNote` and must appear on the page.
- Source attribution (EPA ECHO SDWA, EPA service areas, CDC/ATSDR SVI, Census TIGER/Line,
  U.S. Drought Monitor) must remain visible.
- No other visual, palette, or typographic commitment exists. The incumbent look —
  rounded white cards on a light gray ground, Inter, teal accent, four-metric KPI strip —
  is explicitly **not** a commitment. The user has identified it as reading as
  machine-generated and has authorized full visual replacement.

## Evidence on Hand

Real, and safe to display:

- Live API: `https://water-api.scottcampbell.io/metadata`, `/summary`, `/systems`,
  `/systems/{pwsid}`.
- Current run, scored 2026-06-28, model version 0.1.0: 16,339 records. Tier counts —
  Critical Review 0, High Review 188, Moderate Review 756, Monitor 6,719,
  Lower Priority 8,676.
- Top counties by high-review count: Columbiana 13, Mahoning 11, Summit 11,
  Montgomery 9, Clark 8, Franklin 8, Ashtabula 7, Stark 7, Trumbull 7, Richland 6,
  Wayne 6, Seneca 5. The leading cluster is the northeast Ohio industrial corridor.
- Geography provenance: 207 system-sourced service areas, 870 modeled service areas,
  15,070 approximate locations, 192 unmatched. 3,751 systems have source-water
  protection area coverage.
- Data quality: 22 of 22 validation checks pass.
- Written case study at `docs/portfolio_case_study.md`; methodology at
  `methodology_notes.md`; weights at `config/scoring_weights.yaml`.

Absences that must not be fabricated: no Ohio SRF export was staged in this run, so
funding-gap evidence is partial by design. There are no users, customers, testimonials,
adoption figures, agency endorsements, or performance benchmarks. Critical Review is
genuinely zero — that is a real result, not a loading state, and must not be dressed up.

## Product Principles

1. **Lead with the finding, not the record count.** The reviewer's first question is
   which systems and why, never how many rows exist.
2. **Every number carries its provenance.** A score is only credible on this surface if
   its components and its geometry confidence are reachable from it.
3. **State the limits at full size.** Approximate geography, zero Critical Review, and
   unstaged SRF data are shown as findings about the model, not hidden as caveats.
4. **Screening, never adjudication.** No wording, color, or icon may imply that a listed
   system is unsafe or in violation.
5. **One page, two depths.** The narrative and the working instrument share a URL; the
   handoff between them is designed, not accidental.

## Accessibility & Inclusion

WCAG 2.1 AA is the working standard, already met by the incumbent build and not to be
regressed: visible focus, keyboard-operable table and detail flow, real form labels,
native disclosure elements, 16px minimum control text, ≥4.5:1 body contrast in both
themes, and a skip link. Tier color is never the sole carrier of tier meaning.
