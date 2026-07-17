# HANDOFF — MagneticAnomaly portfolio mockup componentization

> **Read this first.** This is a verbose handoff for the next session/instance
> (SI) picking up the MagneticAnomaly portfolio work. It captures every
> concern Eric raised, every problem we hit, the architectural root cause, and a
> concrete refactor plan. The short version: **the mockups are not componentized
> enough — the desktop frame is not a shared component, so the new hybrid
> variant reinvented it at the wrong size. Fix that, then wire screenshots.**

---

## 0. TL;DR — where things stand right now

- Branch: `worktree-magneticanomaly-5th-project-refactor` (pushed; safe to push —
  MagneticAnomaly is **manual build + FTP, NOT Netlify**, so a push triggers no
  deploy). Latest commit `e9dc80d2`.
- The portfolio is **data-driven**: `src/portfolio/panels-data.js` is the single
  source of truth; `src/App.jsx` generates the GSAP timeline from the `panels`
  array; the footer derives from it. Adding/reordering a panel = one array entry.
- 5 live panels, in order: **Applivation, SourcePrep, HomeColab, DinnerVision,
  DebateHaus.** Applivation was added as panel 1 (before SourcePrep).
- Three mockup variants exist: `desktop-browser`, `dual-phone-image`,
  `dual-phone-placeholder`, and a new `hybrid-desktop-phones` (for Applivation).
- **Applivation is on a placeholder mockup** (branded gradient cells, no real
  screenshots yet). Eric will supply 3 screenshots: **2 phone + 1 desktop**.
- **The open problem (Eric's latest concern):** the mockups are insufficiently
  componentized. The hybrid's desktop is **smaller than SourcePrep's** because
  the desktop frame is not a shared/reusable component. This needs a refactor
  BEFORE wiring screenshots, so every variant composes the same primitives and
  sizing is consistent by construction.

---

## 1. Eric's core concern (in his words, preserved)

Eric has raised this repeatedly across the session. The exact throughline:

1. "These should be templated out and easy to swap in."
2. "we have these animation seted templated out rigt????" (i.e. he believes the
   animations are already templated and expected me to compose them)
3. "What you were supposed to do is [use] the existing animation and then [use]
   the other existing animation." (compose, don't reinvent)
4. "did you build components for these? these all need to be components."
5. "why is the 'desktop screen' size smaller than for SourcePrep — ive said
   several time we need this to be templated?"

**The unifying requirement:** the mockup building blocks — the phone frame, the
desktop frame, and the "reveal" mechanism — must be **reusable React
components**. A new variant must be assembled by composing existing components,
not by writing a new bespoke frame. When two variants both show a desktop, they
must show the **same** desktop (same component → same size). When two variants
both show phones, they must use the **same** `PhoneFrame`. "Easy to swap in"
means: to add a variant you compose components, and to swap real screenshots in
you change data, not code.

---

## 2. The problem in detail — why the hybrid desktop is smaller

### What's shared today (good)
- **`PhoneFrame`** (`src/portfolio/mockups/PhoneFrame.jsx`) — the phone chrome
  (rounded frame, notch, shadow) + an inner scroll container. It takes
  `innerClass`, `cellElements`, and a `staggered` flag. It is reused by
  `DualPhoneImageMockup`, `DualPhonePlaceholderMockup`, and the hybrid. **This
  is the model to follow for the desktop.**

### What's NOT shared (the bug)
- **`DesktopBrowserMockup`** (`src/portfolio/mockups/DesktopBrowserMockup.jsx`)
  is a **monolith**. It owns, in one component:
  1. the entire mockup-column wrapper (`w-full lg:w-7/12 scale-100 sm:scale-75
     md:scale-100 origin-top ... max-md:-ml-2`),
  2. the desktop browser frame chrome (top bar + 3 dots + title),
  3. the xPercent reveal inner (`flex w-[200%] h-full` with 2 screen cells).
  Because the frame chrome is welded to the column wrapper and the xPercent
  inner, **no other variant can reuse just the desktop frame**.

- So when the hybrid needed a desktop for state 2, it **couldn't reuse
  `DesktopBrowserMockup`** (that would have brought the column wrapper + a
  second xPercent inner + the wrong axis). Instead the hybrid file defines its
  own `StaticDesktop` with `w-[85%] aspect-[1078/799]` — a **different size and
  different proportions** than SourcePrep's `w-[110%] ... lg:translate-x-6
  sm:scale-75`. Result: Applivation's desktop visibly shrinks next to
  SourcePrep's. That is the regression Eric spotted.

### Root cause
No `DesktopFrame` component was ever extracted. The desktop chrome lives only
inside the monolithic `DesktopBrowserMockup`. The phone side was done right
(`PhoneFrame`); the desktop side was not. The hybrid exposed the gap.

---

## 3. All the problems we hit this session (chronological, for the record)

1. **First hybrid attempt — wrong concept entirely.** I built a "1 desktop + 2
   phones all on screen at once, all animating together in lockstep" composite.
   Eric's intent was to **compose the two existing templates as the two states
   of one reveal** (state 1 = 2 phones, state 2 = 1 desktop, yPercent reveals
   state 2). Corrected in commit `e9dc80d2`. Lesson: compose, don't invent.

2. **Screenshot count drift.** The first (wrong) hybrid asked for **6**
   screenshots (2 desktop + 4 phone) because it animated every device's 2
   screens. The compositional approach needs only **3** (2 phone + 1 desktop).
   Eric's "2 mobile and one desktop" meant 3 images, not 6.

3. **Desktop sizing inconsistency** (the current open issue, §2). Bespoke
   `StaticDesktop` vs monolithic `DesktopBrowserMockup` → different sizes.

4. **Mobile reveal complexity.** The 2-state reveal needs `overflow-hidden` on
   the stage to clip the off-screen state. On mobile the stage is too narrow
   for 2 phones side by side (2×240px = 504px native > ~327px column), and
   `overflow-hidden` would clip the phones' native overflow before the scale
   transform could shrink them to fit. Resolution in `e9dc80d2`: the reveal runs
   on **md+ only**; mobile shows the **2 phones statically** (exactly like
   dual-phone mobile, which has no `overflow-hidden`); the animated
   `mockup-inner-N` element is `display:none` on mobile so GSAP's yPercent is
   harmless. This works but is a **two-tree** structure (a mobile tree + an md+
   tree) — fragile and worth simplifying in the refactor (see §5).

5. **Staggered phone clipping.** Within the md+ reveal, the staggered phone 2
   (`md:translate-y-16` = +64px) overflowed the 600px stage and got clipped by
   the reveal's `overflow-hidden`. Fixed with `md:pb-16` on the state-1 cell so
   the pair sits 64px up and phone 2 reaches the bottom exactly. A symptom of
   composing without a shared layout primitive.

6. **USB-worktree Edit-tool unreliability** (environmental, carried from the
   prior session). On this USB-backed worktree, the `Edit` tool's writes
   sometimes race with the harness shadow-sync and Vite's module-graph cache;
   edits to `App.jsx` did not reliably persist. Workaround: use **Bash
   (python/perl/sed)** for `App.jsx` edits and verify with `grep`/`git diff`
   before trusting them. New files via `Write` are fine. **Vite's file
   watcher also misses USB FS changes** → the module graph goes stale → restart
   the dev server (`kill :5175` + `npm run dev`) to clear it before verifying.

7. **No image input (model constraint).** The model `glm-5.2:cloud` **crashes on
   any `Read` of a PNG/JPG/WebP** (`API Error 400: model does not support image
   input`). This killed two earlier sessions. **All visual verification is
   text-only**: `browser_evaluate` for `getComputedStyle` / transform-matrix
   parsing / `getBoundingClientRect`, `browser_snapshot` for the a11y tree.
   Never `browser_take_screenshot` + `Read`. Screenshots may be saved to disk
   for the *human* to view, but the agent must never read them back.

8. **MagneticAnomaly deploy confusion (resolved).** Spent effort checking
   whether a push triggers a Netlify build. It does **not** — MagneticAnomaly is
   manual build + FTP. No `netlify.toml`, no deploy job in
   `deploy-websites.yml`, no `NETLIFY_MAGNETICANOMALY` secret. Saved to memory
   (`project_magneticanomaly_deploy.md`). Pushing the feature branch is always
   deploy-safe.

---

## 4. Proposed solution — componentize the mockups

The fix Eric is asking for: extract the shared primitives so every variant
composes them. Then the hybrid's desktop == SourcePrep's desktop by
construction.

### New/extracted components

1. **`DesktopFrame`** (NEW — extract from `DesktopBrowserMockup`)
   - Just the desktop browser chrome: the outer frame (`aspect-[1078/799]`,
     border, rounded, shadow), the top bar (3 dots + title), and a content area.
   - Props: `title`, `children` (the content area body — could be a 2-screen
     xPercent inner, a single static screen, or a placeholder).
   - **No column wrapper, no inner, no axis.** Pure chrome. Reusable.
   - `DesktopBrowserMockup` becomes: column wrapper + `DesktopFrame` (with a
     2-screen xPercent inner inside) — thin composition.
   - The hybrid's state 2 becomes: `DesktopFrame` (with a single static screen
     inside) — **same frame, same size as SourcePrep.**

2. **`RevealInner`** (NEW — optional but recommended) — the 2-state reveal
   mechanism as a reusable template.
   - Props: `innerClass`, `axis` (`'x'|'y'`), `states` (array of 2 React nodes),
     `cellClassName`.
   - Renders the `h-[200%]`/`w-[200%]` inner carrying `innerClass`, with 2
     state cells (`h-1/2` / `w-1/2`). GSAP animates `innerClass` yPercent/xPercent.
   - This is the mechanism currently inlined in every variant. Extracting it
     makes "2-state reveal" a one-liner and removes the per-variant duplication.

3. **`PhoneFrame`** (already exists, already shared) — keep as-is. It already
   takes `innerClass` + `cellElements` + `staggered`. The model to follow.

4. **A graceful cell helper** (NEW — small) — `renderCell(c)`: returns an `<img>`
   if `c.src`, else a branded placeholder (`c.label` / `c.emoji` / `c.barClass`).
   The hybrid already has this inline (`phoneCell` + `StaticDesktop`'s
   branch). Extract it so image-vs-placeholder is one utility, not duplicated.
   This also lets `dual-phone-image` and `dual-phone-placeholder` collapse into
   **one** `dual-phone` variant that renders image-or-placeholder per cell
   (Eric's "easy to swap in" — drop a `src` in, it becomes a real screenshot).

### Target variant set after refactor

- `desktop-browser` = column wrapper + `DesktopFrame` + `RevealInner`(x, 2 screens).
- `dual-phone` (merged) = column wrapper + 2× `PhoneFrame` + shared `RevealInner`(y, per-phone 2 cells) — image-or-placeholder via `renderCell`. Replaces both `dual-phone-image` and `dual-phone-placeholder`.
- `hybrid-desktop-phones` = column wrapper + `RevealInner`(y, [
    state1: 2× `PhoneFrame` (static),
    state2: 1× `DesktopFrame` (static),
  ]) — **reuses `PhoneFrame` and `DesktopFrame` unchanged**, so the desktop is
  identical to SourcePrep's and the phones are identical to HomeColab's.

### Why this satisfies Eric's concerns
- "these all need to be components" → `DesktopFrame`, `PhoneFrame`,
  `RevealInner`, `renderCell` are all reusable components.
- "easy to swap in" → a variant is a composition; a screenshot swap is a data
  field (`src`).
- "desktop screen size smaller than SourcePrep" → impossible after the refactor:
  both use the same `DesktopFrame`.

---

## 5. A note on the mobile two-tree complexity (worth simplifying)

The current hybrid uses a mobile tree (static 2 phones) + an md+ tree (the
reveal), toggled by `md:hidden` / `max-md:hidden`, with the animated
`mockup-inner-N` `display:none` on mobile. It works (verified) but is fragile.

A cleaner approach worth considering in the refactor: make `RevealInner`
**responsive-aware itself** — on viewports too narrow for the content, it
renders only state 1 statically (no `overflow-hidden`, no second state), and the
GSAP tween is gated by `gsap.matchMedia()` so it doesn't fire on narrow
viewports. That would replace the two-tree hack with one tree + a matchMedia
guard in the timeline loop (a small `App.jsx` change: wrap the inner-anim tween
in `gsap.matchMedia('(min-width: 768px)')`). **Decide with Eric** whether that
trade-off (one `App.jsx` matchMedia change) is worth dropping the two-tree hack.
The phone variants already reveal on mobile (their reveal is *inside* each
phone, which has a fixed 520px height, so it works on all viewports); only the
hybrid's *outer* reveal has the mobile-width problem.

---

## 6. Step-by-step for the next SI

1. **Read this doc fully**, then read the existing mockup files:
   `src/portfolio/mockups/{PhoneFrame,DesktopBrowserMockup,DualPhoneImageMockup,DualPhonePlaceholderMockup,HybridDesktopPhonesMockup,HybridDesktopPhonesMockup}.jsx`
   and `src/portfolio/Panel.jsx` and `src/portfolio/panels-data.js`. Also the
   `App.jsx` timeline loop (around the `panels.forEach` / `axis` line, ~line 703).

2. **Extract `DesktopFrame`** (`src/portfolio/mockups/DesktopFrame.jsx`) — the
   desktop chrome only (frame + top bar + content area), taking `title` +
   `children`. No column wrapper, no axis.

3. **Refactor `DesktopBrowserMockup`** to use `DesktopFrame` (column wrapper +
   `DesktopFrame` with the 2-screen xPercent inner inside). Behavior must stay
   identical — verify SourcePrep's panel still matches the baseline oracle
   (inner-2 `tx=-631.5 @ t6`, mid-swipe `-248.89/1431.11 @ t3`, etc.; see
   `.baseline-oracle.json` and the verification JSONs).

4. **(Optional but recommended) Extract `RevealInner`** + **`renderCell`**, and
   merge `dual-phone-image` + `dual-phone-placeholder` into one `dual-phone`
   variant (image-or-placeholder per cell). Update `panels-data.js`
   `mockup.type` for HomeColab/DinnerVision/DebateHaus accordingly. Re-verify all
   three still match the baseline oracle exactly.

5. **Rewrite the hybrid** to compose: `RevealInner`(y, [2×PhoneFrame static,
   1×DesktopFrame static]) — **the `DesktopFrame` here is the SAME component as
   SourcePrep's**, so the desktop is the same size. Drop the bespoke
   `StaticDesktop`. Keep the mobile handling (or adopt the §5 matchMedia
   approach if Eric prefers).

6. **Verify text-only (no image reads!)** at 1600×1000 + 375×812:
   - SourcePrep (now panel 2): inner-2 `tx=-631.5 @ t6` (xPercent unchanged),
     mid-swipe at t3, desktop frame size == before refactor.
   - Hybrid (panel 1): state 1 = 2 phones (both visible, no clip), state 2 =
     desktop revealed at t2 (inner `ty` 0 → −600). **Desktop frame size ==
     SourcePrep's** (same component).
   - Mobile: 2 phones static, no overflow, desktop not rendered.
   - Pin 15000, 0 console errors, lint 21 (0 new), build clean.
   - Re-run the per-SLOT pattern check against `.baseline-oracle.json` (remember
     the oracle assumed SourcePrep=panel-1; verify the PATTERN, not absolute
     panel-N values, since Applivation is now panel 1).

7. **Wire Eric's screenshots** (once he sends them): drop 2 phone PNGs + 1
   desktop PNG in `public/`, add `src`/`alt` to the three hybrid screens in
   `panels-data.js`. Data-only — no code change. Re-verify.

8. **Commit + push the feature branch** (safe — manual FTP). Ask Eric before
   any push to `main`.

---

## 7. Hard constraints / gotchas (do not violate)

- **NEVER `Read` a PNG/JPG/JPEG/WebP. Never `browser_take_screenshot` + Read.**
  The model crashes. Verification is text-only (`browser_evaluate`,
  `browser_snapshot`).
- **No `Co-Authored-By` trailer** in commits.
- **Don't push `main`** without explicit Eric go-ahead (the *other* SourcePrep
  sites are Netlify-auto-deployed on main; MagneticAnomaly itself is manual FTP
  and safe, but `main` still triggers the other sites' builds). Feature-branch
  pushes are fine.
- **USB worktree**: prefer **Bash (python/perl/sed)** for `App.jsx` edits (Edit
  races the shadow-sync); verify with `grep`/`git diff`; **restart the dev
  server** before verifying (Vite's watcher misses USB FS changes). New files
  via `Write` are fine.
- **Use the project venv** (`.venv/bin/python`, `.venv/bin/pytest`) for any
  Python — not relevant to this frontend task but don't forget.
- **Per-slide feel must stay pixel-identical** (Eric's original hard rule): same
  time per slide, same inner-mockup animation, same swipe; only total section
  length changes (linear in panel count). The refactor must not change any
  existing variant's rendered behavior — only factor it into components.
- **Don't touch the marketing home-page hero/tagline** without explicit go-ahead.
- **The `.baseline-oracle.json`** assumed SourcePrep = panel 1. After the
  Applivation reorder, panel indices shifted. Verify the per-SLOT PATTERN
  (4-unit slot, 1.5-unit inner anim at t0+0.5..t0+2.0, swipes at t0+2.4/2.5/4.0,
  last panel no swipe-out), NOT absolute panel-N values.

---

## 8. File map (worktree: websites/MagneticAnomaly/)

| Path | Role |
|------|------|
| `src/portfolio/panels-data.js` | Single source of truth — the `panels` array |
| `src/portfolio/Panel.jsx` | Generic panel chrome + text column; slots the variant |
| `src/portfolio/Payloads.jsx` | Section wrapper + `.map(panels → <Panel>)` |
| `src/portfolio/mockups/PhoneFrame.jsx` | **Shared** phone chrome + inner (the good model) |
| `src/portfolio/mockups/DesktopBrowserMockup.jsx` | Monolith — **to decompose** into `DesktopFrame` |
| `src/portfolio/mockups/DualPhoneImageMockup.jsx` | 2 phones w/ image cells |
| `src/portfolio/mockups/DualPhonePlaceholderMockup.jsx` | 2 phones w/ placeholder cells |
| `src/portfolio/mockups/HybridDesktopPhonesMockup.jsx` | **NEW, needs refactor** — has bespoke `StaticDesktop` (wrong size) |
| `src/portfolio/mockups/index.js` | `mockupVariants` map: type → component |
| `src/App.jsx` | GSAP timeline loop generated from `panels` (axis logic ~line 706) |
| `.baseline-oracle.json` | Phase-0 reference values (SourcePrep=panel-1 assumption) |
| `.applivation-verification.json` | Applivation-as-panel-1 verification |
| `.hybrid-variant-verification.json` | Hybrid variant verification (corrected) |
| `app-content/Applivation.md` | Applivation project page (parity w/ others) |
| `public/Applivation-logo.png` | Applivation logo (from the Applivation repo) |

External: Applivation repo at `/Volumes/Thunderbolt/AI/ApplicationBrowser`
(prep project_id `7cdea5e4-c94d-4612-be67-81597da3d6ec`); its marketing copy in
`web/marketing/src/components/{Hero,ProblemSolution,TheSoul}.jsx` (tone-of-voice
source). Tagline: "Job applications made easy." Canonical URL: `applivation.app`.

---

## 9. Verification protocol (text-only — copy/paste the evaluate snippets)

The session's verification JSONs contain working `browser_evaluate` snippets
for: pin-start/end binary search (position:fixed on `#payloads`), transform
matrix parsing (`matrix(a,b,c,d,tx,ty)` → tx=v[4], ty=v[5]; `matrix3d` →
v[12],v[13]), the per-slot inner-anim endpoint check, mid-swipe check, mobile
bounding-box overflow check, and the `display:none`-on-mobile check. Reuse
them. **Set viewport 1600×1000 for desktop, 375×812 for mobile. Always
`await wait(1200)` after `scrollTo` (scrub:1 eases over ~1s).**

---

## 10. Handoff prompt (paste into the next session)

> See the file `HANDOFF_STARTER_PROMPT.md` next to this doc — paste its
> contents (below the first `---`) into a fresh/compacted session to resume.