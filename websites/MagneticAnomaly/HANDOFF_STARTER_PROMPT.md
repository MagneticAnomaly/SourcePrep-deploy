# STARTER PROMPT — MagneticAnomaly mockup componentization (handoff)

Paste everything below this line into a fresh / compacted session to resume.

---

## ⚠️ HARD CONSTRAINT — DO NOT READ IMAGES (carry forward)

The current model (`glm-5.2:cloud`) does NOT support image input. Reading any
PNG/JPG/JPEG/WebP crashes the session with `API Error 400: this model does not
support image input`. This killed earlier sessions.

- NEVER `Read` a `.png`/`.jpg`/`.jpeg`/`.webp` file. Never.
- NEVER `browser_take_screenshot` then `Read` the result.
- All Playwright verification is TEXT-ONLY: `browser_evaluate` for
  `getComputedStyle` / transform-matrix / `getBoundingClientRect`, `browser_snapshot`
  for the a11y tree.

## YOUR FIRST ACTION

Read the full handoff document before doing anything else:

  websites/MagneticAnomaly/HANDOFF_hybrid_componentization.md

It is verbose on purpose — it captures every concern Eric raised, every
problem we hit, the architectural root cause, and a concrete refactor plan.
Do not skim it; the whole point of the handoff is that context was lost.

## WHERE THINGS ARE

- Worktree: `/Volumes/4TB-BAD/HumanAI/CoDRAG/.claude/worktrees/magneticanomaly-5th-project-refactor/websites/MagneticAnomaly`
  (branch `worktree-magneticanomaly-5th-project-refactor`, pushed to origin).
  Dev server: `npm run dev` → Vite on **:5175**. Restart it before verifying
  (USB-drive Vite watcher misses file changes → stale module graph).
- The portfolio is data-driven: `src/portfolio/panels-data.js` (source of
  truth), `src/portfolio/Panel.jsx`, `src/portfolio/Payloads.jsx`,
  `src/portfolio/mockups/*`, and the GSAP timeline loop in `src/App.jsx`
  (~line 703; axis = `type==='desktop-browser' ? 'xPercent' : 'yPercent'`).
- 5 live panels: **Applivation, SourcePrep, HomeColab, DinnerVision, DebateHaus.**
  Applivation is panel 1, on a placeholder `hybrid-desktop-phones` mockup.
- Latest commit `e9dc80d2`. MagneticAnomaly deploys by **manual build + FTP**
  (NOT Netlify) — pushing the feature branch is always deploy-safe; do NOT push
  `main` without Eric's go-ahead.

## WHAT ERIC WANTS (the open task)

The mockups are **insufficiently componentized**. `PhoneFrame` is shared across
the phone variants (good), but the **desktop frame was never extracted as a
shared component** — `DesktopBrowserMockup` is a monolith (column wrapper + frame
+ xPercent inner welded together). So the new hybrid variant reinvented the
desktop as a bespoke `StaticDesktop` at a **different (smaller) size** than
SourcePrep's. Eric has said repeatedly: "these all need to be components,"
"templated out and easy to swap in," "use the existing animation, not a new one."

## THE REFACTOR (see handoff doc §4 for detail)

1. Extract `DesktopFrame` (`src/portfolio/mockups/DesktopFrame.jsx`) — desktop
   chrome only (frame + top bar + content area), props `title` + `children`.
   No column wrapper, no axis.
2. Refactor `DesktopBrowserMockup` to use `DesktopFrame`. Behavior must stay
   identical (verify against `.baseline-oracle.json`: SourcePrep inner-2
   `tx=-631.5 @ t6`, mid-swipe `-248.89/1431.11 @ t3`).
3. (Recommended) Extract `RevealInner` (the h-[200%]/w-[200%] + innerClass 2-state
   mechanism) and `renderCell` (image-or-placeholder). Merge
   `dual-phone-image` + `dual-phone-placeholder` into one `dual-phone` variant.
4. Rewrite `HybridDesktopPhonesMockup` to compose: `RevealInner`(y, [2×PhoneFrame
   static, 1×DesktopFrame static]) — the `DesktopFrame` is the SAME component as
   SourcePrep's, so the desktop is the same size. Drop the bespoke `StaticDesktop`.
   (Decide with Eric whether to keep the mobile two-tree hack or switch to a
   `gsap.matchMedia('(min-width:768px)')` guard in the App.jsx timeline loop —
   handoff §5.)
5. Verify text-only at 1600×1000 + 375×812: SourcePrep unchanged; hybrid state1 =
   2 phones (no clip), state2 = desktop revealed at t2 (inner ty 0→−600),
   **desktop size == SourcePrep's**; mobile 2 phones static, no overflow; pin
   15000; 0 console errors; lint 21 (0 new); build clean. Verify the per-SLOT
   PATTERN (the `.baseline-oracle.json` assumed SourcePrep=panel-1; Applivation
   is now panel 1, so check the pattern, not absolute panel-N values).
6. Then wire Eric's screenshots when he sends them: 2 phone PNGs + 1 desktop PNG
   in `public/`, add `src`/`alt` to the three hybrid screens in `panels-data.js`
   (data-only). Re-verify.
7. Commit on the feature branch. Push the feature branch (safe). Ask Eric before
   pushing `main`. No `Co-Authored-By` trailer.

## GOTCHAS (handoff §7 has the full list)

- No image reads (this model). Text-only verification.
- USB worktree: prefer Bash (python/perl/sed) for `App.jsx` edits; verify with
  grep/git diff; restart dev server before verifying. New files via Write OK.
- Per-slide feel must stay pixel-identical — the refactor must NOT change any
  existing variant's rendered behavior, only factor it into components.
- `panels` is a module-level const; if it ever becomes dynamic, call
  `ScrollTrigger.refresh()` after the update.
- Don't touch the marketing home-page hero/tagline without explicit go-ahead.