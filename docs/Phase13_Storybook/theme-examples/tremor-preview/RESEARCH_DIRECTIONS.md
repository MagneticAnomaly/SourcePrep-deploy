# Research-Backed Design Directions (Phase 13 Expansion)

These four additional visual directions are grounded in specific design research, historical precedents, and enterprise best practices. They explore how Prep can position itself through distinct "postures" — from an expressive creative tool to a disciplined enterprise infrastructure.

## Direction I: Studio Collage (The "Cranbrook" Posture)
**Inspiration:** Cranbrook Academy of Art (late 80s/90s), CalArts, "Authorial" Design
**Keywords:** Expressive, Layered, Asymmetric, Organic

- **Typography:** `Playfair Display` (Serif Headings) + `Space Mono` (Tech Body). A collision of "old world" authority and "new world" code.
- **Color:** Earthy, paper-like tones (`#fefce8`) with bold, burnt orange (`#c2410c`) and denim blue accents.
- **Shapes:** Mixed border radii (some sharp, some pill), layered elements, overlapping cards.
- **Layout:** "Deconstructed" grid. Elements are placed to create tension and rhythm rather than strict alignment.
- **Why it fits:** Positions coding as a *creative act*. Prep isn't just a utility; it's a studio tool for the "code artisan."

## Direction J: Yale Grid (The "Academic" Posture)
**Inspiration:** Yale School of Art (Dan Michaelson, Sheila Levrant de Bretteville), brutalist academic websites, typographic discipline.
**Keywords:** Semantic, Quiet, Rigorous, Timeless

- **Typography:** `Public Sans` (or `Helvetica`) + `JetBrains Mono`. Relying entirely on weight, size, and indentation for hierarchy.
- **Color:** Oxford Blue (`#1e3a8a`) and grayscale. Very restrained. Color is used *only* for semantic meaning (status, links), never for decoration.
- **Shapes:** Rectangular, sharp, minimal shadows.
- **Layout:** Strict multi-column grids. High information density but with comfortable leading (line-height).
- **Why it fits:** Appeals to the "serious engineer." It says: "We respect your intelligence. No fluff, just data."

## Direction K: Inclusive Focus (The "Human" Posture)
**Inspiration:** SVA Interaction Design, Microsoft Fluent 2, WCAG AAA standards.
**Keywords:** Clarity, Calm, Accessible, High-Vis

- **Typography:** `Atkinson Hyperlegible` (Braille Institute) + `JetBrains Mono`. Designed specifically for maximum readability.
- **Color:** Certified high-contrast pairs. Strong Blue (`#2563eb`) on White/Black. Clear distinction between interactive and static elements.
- **Shapes:** Large, friendly touch targets (44px+). Thick, clear focus rings (`3px solid black/white`).
- **Layout:** Single-column or distinct 2-column. Reduced noise. "Zen mode" by default.
- **Why it fits:** Cognitive load management. AI coding is overwhelming; Prep should be the calm center of the storm.

## Direction L: Enterprise Console (The "Systems" Posture)
**Inspiration:** IBM Carbon, Atlassian Design System, Bloomberg Terminal.
**Keywords:** Dense, Governed, Productive, Trusted

- **Typography:** `IBM Plex Sans` + `IBM Plex Mono`. The typeface of global infrastructure.
- **Color:** Cool Grays (`#f1f5f9` to `#0f172a`) and systemic blues. Status colors are standardized (Red/Yellow/Green).
- **Shapes:** Technical, tight radii (2px-4px). "Boxy" aesthetics. High-density data tables.
- **Layout:** Dashboard-first. Sidebars, tables, and dense metrics. Optimized for "scanning" rather than "reading."
- **Why it fits:** For the CTO/VP Engineering buyer. It looks like "infrastructure" that can be deployed to 1,000 seats safely.

---

## Implementation Notes

- **Fonts:** All added to `index.html` (Playfair, Public Sans, Atkinson, IBM Plex).
- **Themes:** `direction-i.css` through `direction-l.css` implement distinct `border-radius`, `shadow`, and `color` tokens.
- **Heroes:** Unique React components (`StudioHero`, etc.) demonstrate the layout philosophy of each direction beyond just CSS changes.
