---
name: PandaSet
description: Clear portfolio analysis in warm light, with panda ink and bamboo-green accents.
colors:
  bamboo: "#39734f"
  bamboo-hover: "#2b5c3e"
  canvas: "#f3f1e8"
  surface: "#fcfbf6"
  raised: "#e8e7de"
  panel-deep: "#dde9de"
  selected: "#e2ebe0"
  ink: "#171b18"
  muted: "#5c645d"
  border: "#cdd2ca"
  control-border: "#788379"
  comparison: "#737e75"
  ink-on-accent: "#ffffff"
  positive: "#286b47"
  negative: "#a7473f"
  negative-surface: "#f3e4e0"
  warning: "#86580f"
  overlay: "#171b18e6"
typography:
  display:
    fontFamily: "Instrument Serif, Georgia, serif"
    fontSize: "2.6875rem"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-0.6px"
  body:
    fontFamily: "DM Sans, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
rounded:
  sm: "5px"
  md: "7px"
  xs: "3px"
spacing:
  base: "24px"
components:
  button-primary:
    backgroundColor: "{colors.bamboo}"
    textColor: "{colors.ink-on-accent}"
    rounded: "{rounded.sm}"
    padding: "11px 17px"
    height: "42px"
  button-subtle:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "11px 17px"
    height: "42px"
---

# Design System: PandaSet

## Overview

**Creative North Star: "Portfolio clarity in warm light."**

PandaSet is a browser-based portfolio workspace for individual investors. Its light warm-neutral foundation brings a softer, less clinical feel to dense performance, risk, holdings, and research views; panda ink supplies crisp hierarchy, while bamboo green marks primary actions and active states. The panda mark carries the same system through its warm-white face, dark patches, and green eyes.

Keep the palette in service of reading financial information at a glance. Preserve the distinction between illustrative sample data, modeled results, and hypothetical scenarios; color is an additional cue, not a replacement for clear labels.

**Key Characteristics:**
- Warm, low-glare neutrals with strong ink contrast.
- Bamboo green is the single primary accent.
- Semantic gains, losses, warnings, and comparisons remain distinct.

## Colors

The palette combines warm paper-like surfaces, near-black panda ink, a restrained bamboo accent, and separate financial status colors.

### Primary
- **Bamboo green**: primary actions, focus indicators, active navigation, and the main performance series.
- **Deep bamboo**: hover and pressed-action treatment.

### Secondary
- **Positive green**: positive performance and risk cues.
- **Negative red** and **warning amber**: loss and caution states; pale negative surfaces carry supporting context.
- **Comparison gray**: benchmarks and secondary series.

### Neutral
- **Warm canvas**: the page background; **warm white**: cards and overlays.
- **Raised neutral**, **pale bamboo tint**, and **selected pale green**: nested panels, selected rows, and focused supporting areas.
- **Panda ink** and **muted green-gray**: primary and supporting text.
- **Soft divider** and **control outline**: quiet section boundaries and more visible interactive field borders.
- **White on accent**: readable text on bamboo action surfaces.

## Typography

**Display Font:** Instrument Serif (with Georgia fallback); **Body Font:** DM Sans (with Arial, sans-serif fallback).

**Character:** A compact sans-serif system keeps portfolio values and controls easy to scan; Instrument Serif adds a quieter editorial contrast to page titles and selected figures.

### Hierarchy
- **Display** (400, 2.6875rem, 1.15): page headings.
- **Title** (500, 1.3125rem, 1.3): section headings.
- **Body** (400, 1rem default): general interface copy.
- **Label** (500–600, 0.75–0.875rem): compact controls, navigation, and data captions.

## Layout

The desktop shell is centered at a maximum width of 1440px, with an 83px header and generous 52px outer gutters at the widest layout. Pages pair compact labels and tables with larger performance or risk panels. The existing responsive stylesheet adjusts the grids through 1200px, 950px, 720px, and 380px breakpoints; this palette change does not alter those layout rules.

## Elevation & Depth

Depth comes primarily from warm tonal layering and thin borders rather than heavy shadows. A restrained ambient shadow lifts dialogs and selected controls; hover and selected states may use a small shadow where already present in the component.

### Shadow Vocabulary
- **Dialog shadow** (`0 18px 70px #171b1820`): separates overlays from the app canvas.
- **Control state shadow** (`0 1px 3px #00000033` or `0 3px 9px #00000033`): small selected or hover feedback.

## Shapes

The form language uses gently rounded panels (7px), standard controls (5px), and tighter badges or nested controls (3px). Thin neutral borders define cards and stronger control outlines aid field affordance; avoid adding decorative outlines where the surface boundary already reads clearly.

## Components

### Buttons
- **Shape:** compact rounded rectangles (5px).
- **Primary:** bamboo-green fill with white text; 42px minimum height and 11px 17px padding.
- **Hover / Focus:** darken to deep bamboo on hover; use a visible 2px bamboo focus outline on keyboard focus.
- **Secondary / Ghost:** transparent warm-surface controls with a clear control outline; hover adds a raised-neutral fill.

### Cards / Containers
- **Corner Style:** 7px on common analysis panels.
- **Background:** warm white over warm canvas; raised and pale-green tints distinguish nested context.
- **Shadow Strategy:** border and tonal contrast first; reserve stronger elevation for dialogs.
- **Border:** 1px soft neutral divider.
- **Internal Padding:** commonly 24px, with denser page-specific variants.

### Inputs / Fields
- **Style:** warm white fill, visible control outline, and 4–5px radius.
- **Focus:** 2px bamboo outline with offset, or a bamboo outline on the containing field.

### Navigation
- Warm-white header with a thin divider; muted links become panda ink on hover.
- Active route uses a bamboo underline and stronger text weight; retain visible keyboard focus.

### Signature Component
- **Panda mark:** warm-white face, panda-ink patches and mouth, and bamboo-green eyes. Keep it legible at the compact header mark size.

## Do's and Don'ts

### Do:
- **Do** use bamboo green for primary actions, focus, active states, and the lead performance series.
- **Do** keep negative, positive, warning, and comparison cues distinct from one another.
- **Do** preserve visible sample-data and modeled-result labels.

### Don't:
- **Don't** return page backgrounds or card surfaces to the former dark theme.
- **Don't** use the accent as a substitute for semantic gain or loss colors.

- **Don't** imply sample portfolio values are live market or brokerage data.
