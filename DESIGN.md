# Design

The public index at `web/` is built as a **printed federal reference volume**, not as a
dashboard. Structure is carried by hairline rules, register marks and column discipline.
There is no card, no drop shadow and no corner radius anywhere in the system.

## Non-negotiables

1. **No cards.** Grouping is done with rules and whitespace. If something needs a
   container, it needs a rule above it, not a box around it.
2. **No corner radius.** `border-radius` is `0` globally, including on Leaflet's controls.
3. **No drop shadows.** Every `box-shadow` in the stylesheet is an inset hairline or
   `none`. A shadow used for elevation is a bug.
4. **No eyebrows, no section numbering, no scroll cues, no decorative status dots.**
5. **No em dashes or en dashes in any visible string.** Use a period, a comma, or a
   plain hyphen. This is enforced by a scan, not by taste.
6. **Ink is never `#000`.** Not in either theme, not in the print stylesheet.
7. **One family.** Archivo variable only. No second typeface, no icon font, no emoji.

## Type

Archivo variable, self-hosted at `web/fonts/`, preloaded, `font-display: swap`. It is a
grotesque with both a weight axis (100 to 900) and a **width axis (62 to 125)**. The width
axis does the work a second family would normally do:

| Role | Size | Width | Weight |
|---|---|---|---|
| Finding statement | `clamp(2.3rem, 4.3vw, 3.9rem)` | 108 to 118 | 830 |
| Section heading | `clamp(1.15rem, 2vw, 1.5rem)` | 88 | 760 |
| Body and table | 15px / 13.5px | 100 | 400 to 620 |
| Column labels, running heads | 11.5px, tracked `0.13em`, uppercase | 78 | 640 |

Nothing renders below **11px**. Figures are tabular lining throughout
(`font-variant-numeric: tabular-nums lining-nums`).

## Colour

The palette is monochrome stock and ink plus **one saturated signal**. There is no brand
accent; the review ramp is the entire colour system.

| Token | Light | Dark |
|---|---|---|
| `--paper` | `#f7f8fa` | `#0e1113` |
| `--field` | `#e9edf2` | `#1a1f21` |
| `--ink` | `#0c0d10` | `#e7ebf1` |
| `--ink-2` | `#3f434a` | `#a4abb5` |
| `--ink-3` | `#676c75` | `#79808a` |
| `--rule` | `#d7dce3` | `#262c34` |
| `--rule-strong` | `#9ba3ae` | `#464e59` |

The hero choropleth uses a six-step **cool blue** ramp (`--c1` through `--c6`) on
quantile breaks, running pale to deep indigo in light and deep to pale in dark. Equal intervals were tried first and left the top two bands nearly empty,
so the state read as one flat value.

`--signal` (`#d6006b` light, `#ff3d93` dark) is the only saturated colour on the page. It
marks the counties holding high-review systems and the alarm end of the review ramp, and
is never used decoratively.

**This ramp was warm once and that was a mistake.** The first version ran
`#f0eee7 / #e7d8c2 / #e0b993 / #d79366 / #c96a41 / #a3341a`, which is the banned
cream-to-clay family almost value for value. If a warm neutral or an earth-tone accent
starts creeping back into this file, that is the regression.

Review ramp, used for map markers, legend swatches and index bars only:

| Tier | Light | Dark |
|---|---|---|
| Lower Priority | `#c6d4e4` | `#29354a` |
| Monitor | `#93aacb` | `#3f5878` |
| Moderate Review | `#5c76a3` | `#6484ae` |
| High Review | `#d6006b` | `#ff3d93` |
| Critical Review | `#7a0039` | `#ff9ecb` |

The ground carries a slight temperature drift (two fixed radial gradients toward
`--paper-warm` and `--paper-cool`) so it reads as a printed sheet rather than a flat fill.

**Banned palette family.** Warm-cream backgrounds, clay and oxblood accents, and warm
near-black text are the documented AI-default family. Do not reintroduce
`#edede8`-through-`#f7f5f1` grounds, `#b6553a`-family accents, or `#1b1814`-family ink.

**Every colour in this system sits on the cool side of neutral.** The whole palette was
audited channel by channel: no hex has red leading blue by 6 or more. That is the check to
re-run, not a judgement about whether something "looks" warm. It caught three values a
visual pass missed: the modelled-boundary gold `#9a6a12` (the banned brass family), the
error-banner field `#e8ded6` (the banned cream family), and the dark-theme ink `#eceae3`.

**The basemap counts too.** OpenStreetMap raster tiles ship warm land fill, green forest
and pink motorways, which was the largest warm surface on the page and fought everything
else. `--map-tile-filter` neutralises them in both themes: `grayscale(1) contrast(0.82)
brightness(1.08)` in light. The tiles are ground; the tier markers carry the signal.

## Charts

One bar treatment everywhere: a 6px bar on a hairline baseline, never a filled track.

Compositions get a stacked bar plus a ruled key: the seven scoring weights, and the four
geometry-provenance tiers. Segments take the `--c1` to `--c6` ramp with a hairline edge,
because the palest step sits close to the paper and the largest share would otherwise read
as a gap. Anything that is not a share of the whole, like the data-quality deduction, sits
below a rule with an outlined swatch rather than a filled one.

**No decorative fill.** A dot-matrix block once filled the short column under the
limitations. If a column looks empty it needs content, and the content that belonged there
was the geometry breakdown that makes the caveat above it concrete.
Bars carry the colour of what they measure. Review-tier bars take their tier's ramp colour;
the county chart measures high-review counts, so its bars take `--tier-high`; component
bars inside a record are neutral `--ink-3`, because there the figure is the point.

## The tier mark

Review tier is rendered as **five notches filled to the tier's step**, in `--ink`, beside
the tier name. Ordinality is carried by the count, not by hue, so the ranking survives
greyscale, colour-blindness and a black-and-white print. The ramp colour is deliberately
**not** used to fill the notches; that frees the ramp to be a real signal on the map
without owning the accessibility burden.

Colour is never the sole carrier of tier meaning anywhere in the interface.

## Interactive plate

The hero map answers to a pointer: moving over a county writes its systems, high-review
count and mean score into `#heroReadout`, which is `role="status" aria-live="polite"`. At
rest the readout carries a hint rather than sitting blank, because a blank line says
nothing about whether the map is interactive; under `hover: none` the hint points at the
county list instead. The readout gets its own row in the caption grid so it can never wrap
into the plate's corner mark.

Keyboard users are served by the ranked county chart below rather than by 88 focusable SVG
paths. That is a deliberate trade, recorded here so it is not mistaken for an oversight.

## Motion

Three moments, each with a job. Nothing else animates.

1. **The linked update.** A filter change sets `data-updating` on the app shell, fading
   every `.settles` region to 0.45 in 90ms and returning it over 340ms on an exponential
   ease-out, so one control visibly propagates across the map, both indexes, the table and
   the record as a single update rather than four independent refreshes.
2. **The plate entrance.** The 88 counties stagger in at `calc(var(--i) * 7ms)`, a ~615ms
   cascade that draws the eye to the page's focal element once.
3. **Map selection.** Choosing a system pans the Leaflet map to it, which is spatial
   feedback for the selection, not decoration.

Bars land rather than grow, because animating `width` forces layout. All three collapse
under `prefers-reduced-motion`.

## Structure

The page is a hero followed by two asymmetric bands, not a single stacked column.

1. **Hero.** The finding at display scale on the left, with the counts written into the
   sentence itself. On the right, a custom SVG choropleth of Ohio's 88 counties drawn from
   `web/data/ohio_counties.geojson`, shaded by mean review-priority score with proportional
   marks on counties holding high-review systems. It depends on no API call and paints
   before the first request. Hard capacity: nothing else competes inside this block, and
   the ledger beneath it must never echo the headline numbers.
   The plate is sized to its artwork, not the other way round. The map's viewBox is
   620x742, so at a 500px height cap it is 418px wide; the hero's map column is 452px so
   the plate hugs it. Giving the plate a wider fixed box letterboxes the state and strands
   the corner register marks in empty gutters.
2. **Survey band.** Street map in the wide column, tier distribution and county ranking in
   the narrow one. `1.5fr / 1fr`, stretched so both columns finish together.
3. **Instrument band.** Filters and the ranked table in the wide column, the selected-system
   record sticky beside it in the narrow one, so choosing a row does not mean scrolling.
   `1.55fr / 1fr`.
4. **Method** and **what this does not establish**, at equal weight.

Columns are separated by a hairline column rule and whitespace. Panels are never boxes.
Both bands collapse to one column below 1080px, where the record stops being sticky.

The table sheds columns twice. A container query drops leading driver and geometry when the
panel is under 860px, because eight columns in a 720px panel wrap every cell to three lines;
the record repeats both fields anyway. Below 640px it also drops PWSID and county, folds the
tier label to its notches, and switches to `table-layout: fixed`.

**The fixed layout is the part that matters.** Under auto layout the name column sizes to
its content, so a long system name pushes the table wider than the phone however tight the
other columns get. Fixed layout is what lets the name truncate instead. The tier label is
clipped rather than `display: none`, so it still reaches a screen reader.

No count from a single model run is hardcoded in markup, including inside the hero plate's
accessible name. Every figure is filled from the API at render time.

The one deliberate exception is the seven component weights, which are mirrored as static
markup in `index.html` and as label strings in `app.js`. The API does not expose them, and
they are model constants rather than run results. They must be kept in step with
`config/scoring_weights.yaml` by hand; if the API ever serves them, read them instead.

## Constraints that bind any future change

- Vanilla HTML, CSS and JS. No build step, no framework, no bundler.
- CSP is `script-src 'self'` and `font-src 'self'`. No inline `<script>`, no external
  fonts or stylesheets. Vendor anything new into `web/`.
- `app.js` renders through `innerHTML` templates keyed to specific IDs and classes.
  Changing markup means changing both files together.
- WCAG 2.1 AA, verified in-browser in both themes rather than asserted. The current build
  has zero contrast failures at the computed-style level.
