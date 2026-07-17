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
    id: 'applivation',
    status: 'live',
    name: 'Applivation',
    tag: '[ iOS / APP ]',
    icon: '/Applivation-logo.png',
    url: 'https://applivation.app',
    tagline: 'Job applications made easy.',
    blurb: 'Applivation is an autofill for job applications. It maps your saved career history onto grueling ATS forms in seconds, syncs invisibly through iCloud, and never auto-submits — you review and confirm every field. Privacy-first across iPhone, iPad, and Mac, with no third-party accounts and zero data mining.',
    bullets: [
      'Autofill ATS Forms in Seconds',
      'iCloud Sync, Zero Data Mining',
      'Review & Confirm — Never Auto-Submits',
    ],
    // STOPGAP mockup: Applivation is a phone app → dual-phone variant. Using
    // dual-phone-placeholder (bespoke cells) until Eric supplies real App Store
    // screenshots. To go live: swap `type` to 'dual-phone-image' and replace
    // `phones` with a HomeColab-shaped {cells:[{cellClass,src,alt}]} structure
    // pointing at the screenshot files dropped into public/. The timeline loop
    // picks up the yPercent axis automatically — no App.jsx edit needed.
    mockup: {
      type: 'dual-phone-placeholder',
      phones: [
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-t from-void to-[#0a1830] flex items-center justify-center p-4', labelClass: 'font-mono flex-col flex text-center text-[10px] text-[#6EA8FE]', emoji: '🔒', label: 'VAULT' },
            { cellClass: 'h-1/2 w-full bg-[#050508] border-t border-white/5 flex items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-telemetry', label: 'ATS FORM' },
          ],
        },
        {
          cells: [
            { cellClass: 'h-1/2 w-full bg-gradient-to-b from-void to-[#111128] flex items-center justify-center p-4', labelClass: 'font-mono flex-col flex text-center text-[10px] text-[#6EA8FE]', emoji: '✨', label: 'AUTOFILL' },
            { cellClass: 'h-1/2 w-full bg-[#030305] border-t border-white/5 flex flex-col items-center justify-center p-4', labelClass: 'font-mono text-[10px] text-[#6EA8FE] mb-3', label: 'CONFIRM', barClass: 'w-full h-10 rounded-lg bg-gradient-to-r from-[#6EA8FE]/20 to-[#6EA8FE]/5 border border-[#6EA8FE]/30' },
          ],
        },
      ],
    },
  },

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
];

export default panels;