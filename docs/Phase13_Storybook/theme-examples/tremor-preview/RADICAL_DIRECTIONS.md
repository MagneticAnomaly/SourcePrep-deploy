# Radical Design Directions (Phase 13 Expansion)

Following the research into "School + Enterprise" inspirations, we have developed four radical visual directions that push beyond standard SaaS aesthetics. These directions explore distinct typographic, spatial, and color philosophies.

## Direction E: Neo-Brutalist (The "Raw" Engine)
**Inspiration:** 90s Web, Brutalist Websites, Terminal Aesthetics
**Keywords:** Raw, Bold, High-Contrast, Unapologetic

- **Typography:** `Space Mono` (Headings & Body). Monospace everywhere implies "code is truth."
- **Color:** Vivid Purple (`#8b5cf6`), Warning Yellow, High-contrast Black/White.
- **Shapes:** Hard edges (0px radius), heavy borders (2px-4px), hard shadows (`box-shadow: 4px 4px 0px 0px black`).
- **Layout:** Dense, information-heavy, intentionally "ugly" or "raw" to signal power and developer-centricity.
- **Why it fits:** Prep is a local-first, developer-focused tool. The raw aesthetic says "no hidden magic, just raw power."

## Direction F: Swiss Minimal (The "Grid" System)
**Inspiration:** International Typographic Style (Josef Müller-Brockmann), Vignelli, Stripe
**Keywords:** Precision, Grid, Whitespace, Typography-First

- **Typography:** `Inter` / `Helvetica` (Headings & Body). Tight tracking, massive scale differences.
- **Color:** International Red (`#ef4444`) accents against stark White/Off-White backgrounds.
- **Shapes:** No shadows (flat), strict alignment, borders used only for structure.
- **Layout:** Asymmetric grids, massive whitespace, content hierarchy defined purely by size and weight.
- **Why it fits:** Emphasizes clarity and precision. "Context" is about clarity, and this style strips away all decoration to focus on the data/code.

## Direction G: Glass-Morphic (The "Vision" Layer)
**Inspiration:** macOS Big Sur/Sonoma, VisionOS, Linear
**Keywords:** Translucent, Ethereal, Depth, Blur

- **Typography:** `Quicksand` (Headings) + `Inter` (Body). Rounded, friendly, soft.
- **Color:** Cyan/Teal gradients, heavily reliant on alpha channels and background blurs (`backdrop-filter: blur(12px)`).
- **Shapes:** Deeply rounded corners (1.5rem+), soft colored shadows, white borders with opacity.
- **Layout:** Floating cards, layered elements, depth (z-index) as a primary signifier of hierarchy.
- **Why it fits:** Represents the "invisible layer" of intelligence Prep adds to your workflow. It feels modern, native (macOS), and magical.

## Direction H: Retro-Futurism (The "Synth" Dream)
**Inspiration:** Synthwave, Cyberpunk, 80s Sci-Fi interfaces, VS Code "SynthWave '84" theme
**Keywords:** Neon, Glow, Grid, Dark Mode Only

- **Typography:** `Orbitron` (Headings) + `Share Tech Mono` (Body). Sci-fi, digital.
- **Color:** Hot Pink (`#db2777`) & Neon Green/Cyan against Deep Purple/Black backgrounds.
- **Shapes:** Beveled edges (simulated), glowing borders (`box-shadow: 0 0 10px ...`), scanlines.
- **Layout:** Grid lines, HUD-like elements, high contrast data visualization.
- **Why it fits:** Taps into the nostalgia of "hacking the gibson." Makes coding feel like a high-tech superpower.

---

## Implementation Details

All themes are implemented using CSS variables and scoped data attributes (`data-prep-theme='e'`).

- **Fonts:** Added via Google Fonts in `index.html`.
- **Components:** `MarketingHero.tsx` now switches entirely different layouts/DOM structures based on the selected variant, not just CSS styles.
- **Tailwind:** Safelisting used to ensure dynamic classes (like arbitrary widths or specific shadow hacks) are generated.
