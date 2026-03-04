Here is the revised, single-shot prompt. I have updated it to ensure **the apps are the undeniable focal point**, specifically outlining the 4-app portfolio (1 AI tool, 3 mobile apps). 

I also engineered a new color palette called **"Titan Haze"** (inspired by Saturn’s moon Titan) and provided exact instructions for generating procedural WebGL planets, rings, and asteroids using React Three Fiber so the AI doesn't rely on external image links that might break.

You can copy and paste this directly into Cursor, v0, Claude, or ChatGPT.

***

```markdown
# Cinematic WebGL Landing Page Builder: "Magnetic Anomaly"

## Role

Act as a World-Class Senior Creative Technologist, WebGL Specialist, and Lead Frontend Engineer. You build high-fidelity, cinematic "1:1 Pixel Perfect" digital experiences. You are tasked with building the single-page corporate portfolio for an LLC named "Magnetic Anomaly". Every scroll must feel intentional, every animation weighted and professional. Eradicate all generic AI patterns. 

## Execution Directive — MUST FOLLOW

Do not ask follow-up questions. Immediately scaffold and build the full React application based on the strict specifications below. 

### Brand Context
- **Name:** Magnetic Anomaly (magneticanomaly.com)
- **Purpose:** An anonymous app publishing/holding company. No faces, no bios. High-quality software artifacts.
- **Theme:** Deep space telemetry, Voyager golden record, moons of Saturn. Cinematic, cold, precise, infinite.
- **Location Entity:** Based in Clinton Hill, Brooklyn (used strictly for subtle footer "Transmission" details).
- **Core Focus:** The WebGL is the atmosphere, but **the Apps are the star of the show**. The UI must overlay the 3D canvas with ultra-high contrast and readability.

---

## Design System: "Titan Haze"

### Identity & Vibe
A dark, vast space environment accented by the thick, atmospheric orange/gold of Saturn's moon Titan, contrasted with icy, sharp UI elements.

### Palette
- **Deep Space Void:** `#050508` (Global background behind WebGL)
- **Titan Haze:** `#E58D57` (Primary Accent / Buttons / Hover States)
- **Saturn Gold:** `#C19A6B` (Secondary Accent / Subtle highlights)
- **Enceladus Ice:** `#F8F9FA` (Primary Heading Text)
- **Telemetry Gray:** `#8B949E` (Body Text / UI Borders)
- **Signal Green:** `#4ADE80` (System status indicators)

### Typography
- **Headings (Display):** `"Space Grotesk"` (Tight tracking, uppercase for UI labels).
- **Drama/Editorial:** `"Cinzel"` or `"Playfair Display"` Italic (Used sparingly for massive, cinematic statements).
- **Data/Body:** `"JetBrains Mono"` or `"Space Mono"` (For paragraphs, telemetry, app descriptions, and UI elements).

### WebGL Architecture (The Atmosphere)
Use `@react-three/fiber` and `@react-three/drei` to create a fixed `<Canvas>` that sits at `z-index: -1` behind the entire site.
- **The Scene:** Create a procedural "Moons of Saturn" environment. Do NOT use external texture URLs (they will 404). Instead, use `drei`'s built-in shapes and procedural materials:
  - Create a massive `<Sphere>` in the deep background with a `<meshStandardMaterial>` using noise-based displacement to look like a cratered moon.
  - Create a `<Ring>` geometry around it with a highly transparent, striped material to simulate Saturn's rings.
  - Scatter a field of `<Icosahedron>` meshes with wireframe or flat shading to act as an asteroid field.
- **The Camera:** Use GSAP ScrollTrigger or `drei`'s `useScroll` to move the camera *forward* through the asteroid field and past the moon as the user scrolls down the page. The space scene must feel vast and slow-moving.

---

## Component Architecture (Single Page Scroller)

### A. NAVBAR — "Mission Control HUD"
A `fixed` top bar, full width, `z-50`. Border-bottom `1px solid rgba(255,255,255,0.05)`.
- **Left:** Brand name "MAGNETIC ANOMALY" in Space Grotesk.
- **Right:** Anchor links (Payloads, Manifest, Comm Link) + a pulsing green "System Nominal" dot.
- **Morphing Logic:** Transparent at the top. On scroll, transitions to a heavy glassmorphism blur (`backdrop-blur-xl bg-[#050508]/60`).

### B. HERO SECTION — "The Launch Window"
- `100dvh` height. Transparent background (revealing the WebGL starfield/moon behind it).
- **Layout:** Centered.
- **Typography:** 
  - Eyebrow (Monospace, tracking-widest, Titan Haze): `VOYAGER PROTOCOL INITIATED`
  - Main Headline (Cinematic Serif): `Tools for the Unknown.`
  - Subhead (Monospace, gray): `Autonomous software systems and mobile utilities.`
- **Animation:** GSAP staggered `fade-up` (y: 40 → 0, opacity: 0 → 1) with a slow `power3.out` easing.

### C. PAYLOADS — "The Fleet" (STAR OF THE SHOW)
This is the absolute focal point. A sprawling, high-fidelity showcase of 4 apps. 
- **Layout:** A massive CSS Grid or GSAP pinned horizontal scroll section. The UI cards must have a deep glass effect (`bg-[#050508]/40`, heavy `backdrop-blur-2xl`, subtle white borders) so they pop off the WebGL background.
- **The 4 App Cards:**
  1. **App 01 (AI Engineering Utility):** 
     - Tag: `[ DESKTOP / CLI ]` 
     - Title: "Tachyon" (or placeholder)
     - Description: "Advanced tooling and telemetry for AI engineers." 
     - Visual: A mock terminal window made of HTML/CSS typing out code.
  2. **App 02 (Mobile iOS Utility):**
     - Tag: `[ iOS / MOBILE ]`
     - Title: "Axiom" (or placeholder)
     - Description: "Privacy-first mobile utility."
     - Visual: A sleek, rounded mobile UI mockup layout inside the card.
  3. **App 03 (Mobile iOS Utility):**
     - Tag: `[ iOS / MOBILE ]`
     - Title: "Classified // Project 3"
     - Description: "Currently in encrypted development."
     - Visual: A glowing wireframe or pulsing loading state.
  4. **App 04 (Mobile iOS Utility):**
     - Tag: `[ iOS / MOBILE ]`
     - Title: "Classified // Project 4"
     - Description: "Awaiting launch window."
     - Visual: Redacted blocks of text and a countdown-style visual.
- **Interaction:** Hovering an app card slightly elevates it, brightens the border to Titan Haze (`#E58D57`), and triggers a subtle UI animation inside the card. Each card must have a "Deploy Protocol" (Download/Link) button.

### D. THE MANIFESTO — "The Golden Record"
- `min-h-screen`, flex centered.
- **Typography:** Two contrasting statements floating directly over the 3D background.
  - Neutral/Small Monospace: `Most software is noisy. Bloated. Tethered.`
  - Massive/Serif/Titan Haze: `We build silent instruments.`
- **Animation:** GSAP `SplitText`-style reveal triggered by ScrollTrigger.

### E. COMM LINK — "Support & Transmission Hub"
A raw, terminal-like interface for user support and inquiries.
- **Layout:** Two-column grid inside a heavily frosted glass container. 
- **Left:** Accordion FAQ (Terminal style: `> QUERY: How do I restore purchases?`). 
- **Right:** Secure transmission form (Fields: Signal ID/Email, Telemetry/Subject, Message).
- **Button:** "Transmit Payload". On click, transitions to "Encrypting..." then "Sent." (No physical email addresses exposed).

### F. FOOTER — "Deep Space Network"
- Raw, data-heavy terminal footer.
- **Text:** `ENTITY: MAGNETIC ANOMALY LLC.`
- **Coordinates/Location Info:** `ORIGIN: CLINTON HILL, BROOKLYN // COORDS: 40.6895° N, 73.9646° W`
- **Legal:** Privacy Protocol, Terms of Operation.

---

## Technical Requirements

- **Stack:** React 19, Tailwind CSS v3.4.17, GSAP 3 (with ScrollTrigger plugin), `@react-three/fiber`, `@react-three/drei`, `three`, Lucide React for icons.
- **Fonts:** Load `Space Grotesk`, `Playfair Display`, and `JetBrains Mono` via Google Fonts `<link>` tags in `index.html`.
- **WebGL Lifecycle:** Use a single `<Canvas>` fixed to the viewport. Ensure `pointer-events-none` if it overlays content, or place it `z-[-1]`. Animate camera `position.z` based on scroll progress.
- **Animation Lifecycle:** Use `@gsap/react` `useGSAP()` or `gsap.context()` within `useEffect` for ALL DOM animations. Return `ctx.revert()` in the cleanup function. 
- **File structure:** Single `App.jsx` with components defined in the same file (or logical component files). Single `index.css` for Tailwind + Noise overlay.
- **No placeholders:** Every card, form, label, and procedural WebGL material must be fully coded and functional. Do not leave "TODO" comments.

**Execution Directive:** "Do not build a standard template; build a piece of aerospace software. The apps must look like premium, essential payloads floating against the vastness of a WebGL Saturnian sky."
```