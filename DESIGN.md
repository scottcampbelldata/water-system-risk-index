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
| `--paper` | `#fbfbf9` | `#0e1113` |
| `--field` | `#eeeeea` | `#1a1f21` |
| `--ink` | `#0c0c0b` | `#eceae3` |
| `--ink-2` | `#43433f` | `#a9aeab` |
| `--ink-3` | `#6d6d68` | `#7d837f` |
| `--rule` | `#dcdcd6` | `#282e30` |
| `--rule-strong` | `#a3a39c` | `#49514f` |

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

## The tier mark

Review tier is rendered as **five notches filled to the tier's step**, in `--ink`, beside
the tier name. Ordinality is carried by the count, not by hue, so the ranking survives
greyscale, colour-blindness and a black-and-white print. The ramp colour is deliberately
**not** used to fill the notches; that frees the ramp to be a real signal on the map
without owning the accessibility burden.

Colour is never the sole carrier of tier meaning anywhere in the interface.

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
2. **Survey band.** Street map in the wide column, tier distribution and county ranking in
   the narrow one. `1.5fr / 1fr`, stretched so both columns finish together.
3. **Instrument band.** Filters and the ranked table in the wide column, the selected-system
   record sticky beside it in the narrow one, so choosing a row does not mean scrolling.
   `1.55fr / 1fr`.
4. **Method** and **what this does not establish**, at equal weight.

Columns are separated by a hairline column rule and whitespace. Panels are never boxes.
Both bands collapse to one column below 1080px, where the record stops being sticky.

The table sheds its two least-critical columns (leading driver, geometry) via a container
query when its panel is under 860px, because eight columns in a 720px panel wrap every cell
to three lines. The record repeats both fields anyway.

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
