// Single source of truth for the Payloads portfolio carousel AND the footer
// SystemIndex. Adding/removing a project is one entry here; the GSAP timeline
// (App.jsx) and the footer both derive from `panels`.
//
// Schema:
//   {
//     id, status: 'live' | 'placeholder',   // SystemIndex filters to status==='live'
//     name, tag, icon, url,                  // url:null for placeholder (excluded from footer)
//     tagline (short — footer + panel <strong> lead),
//     blurb (long — panel body only),
//     bullets: [..],
//     cardOverlay?: boolean,                 // optional hover-gradient overlay (SourcePrep only)
//     mockup: { type, ...variantProps }
//   }
//
// Mockup variants (the only per-panel variation):
//   - desktop-browser:        one browser frame, inner anim xPercent
//   - dual-phone-image:        two phone frames w/ remote screenshots, inner anim yPercent
//   - dual-phone-placeholder:  two phone frames w/ bespoke gradient/label cells, inner anim yPercent
//
// GUARDRAIL: `panels` is a module-level const. If it ever becomes dynamic
// (state/fetch), ScrollTrigger.refresh() must run after the post-update commit —
// pin start/end are measured from the DOM at creation time.

export const panels = [
  {
    id: 'sourceprep',
    status: 'live',
    name: 'SourcePrep',
    tag: '[ DESKTOP / APP ]',
    icon: '/SourcePrep-Logo2.png',
    url: 'https://sourceprep.io',
    tagline: 'The Context Engine for AI-Assisted Software Engineering.',
    blurb: 'SourcePrep bridges the gap between massive, complex codebases and LLMs by providing precise, graph-augmented context. It uses advanced AST parsing to trace dependencies, effectively fighting Context Bloat and reducing token costs.',
    bullets: [
      'Native Semantic Search (Local ONNX)',
      'Code Graph & Trace Expansion',
      'Smart Token Compression (20:1 ratio)',
    ],
    cardOverlay: true,
    mockup: {
      type: 'desktop-browser',
      title: 'prep-dashboard',
      screens: [
        // BUGFIX (bundled): public/ has Prep-ss1.png / Prep-ss2.png (no "Source"
        // prefix). The pre-refactor JSX referenced /SourcePrep-ss1.png which 404'd.
        { src: '/Prep-ss1.png', alt: 'SourcePrep Screen 1' },
        { src: '/Prep-ss2.png', alt: 'SourcePrep Screen 2' },
      ],
    },
  },

  {
    id: 'homecolab',
    status: 'live',
    name: 'HomeColab',
    tag: '[ iOS / MOBILE ]',
    icon: '/HomeColab-logo.png',
    url: 'https://homecolab.app',
    tagline: 'Find a Home... Together.',
    blurb: 'HomeColab is the ultimate shared workspace for homebuyers and a silent intelligence engine for real estate agents. It replaces messy group texts and notification noise with a structured, intent-driven experience.',
    bullets: [
      'Universal Link Unfurling',
      'Partner Alignment & Heat Scores',
      'Smart Agent Briefings',
    ],
    mockup: {
      type: 'dual-phone-image',
      phones: [
        {
          cells: [
            { cellClass: 'h-1/2 w-full flex items-center justify-center bg-void', src: 'https://homecolab.app/screenshots/SS_01_the_list_.png', alt: 'HomeColab Screen 1' },
            { cellClass: 'h-1/2 w-full flex items-center justify-center bg-void', src: 'https://homecolab.app/screenshots/SS_09_Rank-Compare2.png', alt: 'HomeColab Screen 3' },
          ],
        },
        {
          cells: [
            { cellClass: 'h-1/2 w-full flex items-center justify-center bg-void', src: 'https://homecolab.app/screenshots/SS_02_webview-details.png', alt: 'HomeColab Screen 2' },
            { cellClass: 'h-1/2 w-full flex flex-col items-center justify-center bg-void', src: 'https://homecolab.app/screenshots/SS_10_Rank-OurFavs.png', alt: 'HomeColab Screen 4' },
          ],
        },
      ],
    },
  },

  {
    id: 'dinnervision',
    status: 'live',
    name: 'DinnerVision',
    tag: '[ iOS / MOBILE ]',
    icon: '/DinnerVision_v2.png',
    url: 'https://dinner.vision',
    tagline: 'Turn what you have into what you can cook.',
    blurb: 'An intelligent mobile app designed to eliminate decision fatigue. Harnessing the power of computer vision, it instantly transforms the random ingredients in your fridge into delicious, actionable meal ideas.',
    bullets: [
      'Camera-First Ingredient Detection',
      'Smart Pantry Assumptions',
      'Custom Recipe Generation',
    ],
    mockup: {
      type: 'dual-phone-placeholder',
      phones: [
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-t from-void to-[#201005] flex items-center justify-center p-4', labelClass: 'font-mono flex-col flex text-center text-[10px] text-[#E58D57]', emoji: '📸', label: 'SCAN' },
            { cellClass: 'h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-telemetry', label: 'RECIPE' },
          ],
        },
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-b from-void to-[#111118] flex items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-telemetry', label: 'AI MATCH' },
            { cellClass: 'h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-signal mb-3', label: 'COOK MODE', barClass: 'w-full h-8 rounded-md bg-signal/10 border border-signal/20' },
          ],
        },
      ],
    },
  },

  {
    id: 'debatehaus',
    status: 'live',
    name: 'DebateHaus',
    tag: '[ iOS / MOBILE ]',
    icon: '/DebateHaus_LogoColor.png',
    url: 'https://debate.haus',
    tagline: 'Elevating the Digital Public Square.',
    blurb: 'A video-first platform engineered to elevate the quality of online conversation. Moving beyond toxic comment threads, DebateHaus offers a structured, purpose-built format for civil, good-faith debate between creators, intellectuals, and institutions.',
    bullets: [
      'Structured Pre-Debate Negotiation',
      'Private Video Recording Environment',
      'Co-Creator Publishing & Engagement',
    ],
    mockup: {
      type: 'dual-phone-placeholder',
      phones: [
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-t from-void to-[#101030] flex items-center justify-center p-4', labelClass: 'font-mono flex-col flex text-center text-[10px] text-[#8B949E]', emoji: '🎙️', label: 'INVITE' },
            { cellClass: 'h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-telemetry', label: 'RECORDING' },
          ],
        },
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-b from-void to-[#111118] flex items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-telemetry', label: 'TERMS' },
            { cellClass: 'h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-ice mb-3', label: 'PUBLISHED', barClass: 'w-full h-12 rounded-lg bg-gradient-to-r from-void to-white/5 border border-white/5' },
          ],
        },
      ],
    },
  },

  // --- PLACEHOLDER 5TH ENTRY — mechanism proof, not real content ---
  // status:'placeholder' → renders in the carousel (proves the timeline scales to
  // N=5) but is EXCLUDED from the footer SystemIndex and from SEO meta. Real
  // 5th-project content (copy, logo, screenshots) is a separate follow-up.
  {
    id: 'placeholder-5',
    status: 'placeholder',
    name: 'Coming Soon',
    tag: '[ IN DEVELOPMENT ]',
    icon: null, // null → render a muted monogram tile instead of an <img>
    url: null,
    tagline: 'A new payload is entering orbit.',
    blurb: 'This slot is a placeholder proving the portfolio scales to five projects. The real fifth project — copy, branding, and live mockups — lands here in a follow-up. Everything else about the scroll experience stays identical.',
    bullets: [
      'Mechanism Test — Scales to N=5',
      'Same Per-Slide Feel, +25% Scroll',
      'Real Content Forthcoming',
    ],
    mockup: {
      type: 'dual-phone-placeholder',
      phones: [
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-t from-void to-[#1a1a2a] flex items-center justify-center p-4 border-2 border-dashed border-white/10', labelClass: 'font-mono text-[10px] text-white/30', label: 'PLACEHOLDER' },
            { cellClass: 'h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4 border-2 border-dashed border-white/10', labelClass: 'font-mono text-[10px] text-white/30', label: 'PLACEHOLDER' },
          ],
        },
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-b from-void to-[#1a1a2a] flex items-center justify-center p-4 border-2 border-dashed border-white/10', labelClass: 'font-mono text-[10px] text-white/30', label: 'PLACEHOLDER' },
            { cellClass: 'h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4 border-2 border-dashed border-white/10', labelClass: 'font-mono text-[10px] text-white/30 mb-3', label: 'PLACEHOLDER', barClass: 'w-full h-10 rounded-md bg-white/5 border border-white/10' },
          ],
        },
      ],
    },
  },
];

export default panels;