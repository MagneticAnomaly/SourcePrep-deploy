import { addons } from '@storybook/manager-api';
import { create } from '@storybook/theming';

// Phase 131: restyle the Storybook chrome (sidebar, toolbar, addon panels)
// using the light variant of the "Slate Developer" theme (prepTheme='a').
// Token sources are direction-a.css [data-prep-theme='a'] light-mode block,
// converted from HSL to hex. The story content iframe defaults to dark mode
// + the same theme — see preview.tsx — so visitors see the Slate Developer
// language in both surfaces, light chrome around dark playgrounds.
//
// See docs/Phase131_StorybookCuration/02_visual_design_plan.md for rationale
// and the full token mapping.

const slateDeveloperLight = create({
  base: 'light',

  // Brand. brandImage is served from .storybook/static/ via staticDirs in
  // main.ts; the path is relative to the served root (no /static/ prefix).
  brandTitle: 'SourcePrep · Design System',
  brandUrl: 'https://sourceprep.io',
  brandTarget: '_blank',
  brandImage: './sourceprep-logo.png',

  // App canvas — sidebar and surrounding chrome.
  appBg: '#F8FAFC',           // --background
  appContentBg: '#FFFFFF',    // --surface (story preview area)
  appPreviewBg: '#FFFFFF',    // matches surface for clean transitions
  appBorderColor: '#D9DFE6',  // --border
  appBorderRadius: 6,

  // Top toolbar / footer addon bar.
  barBg: '#F1F4F8',           // --surface-raised
  barTextColor: '#64748B',    // --text-muted
  barSelectedColor: '#2563EB',// --primary
  barHoverColor: '#0F172A',   // --text

  // Body text.
  textColor: '#0F172A',       // --text
  textInverseColor: '#FFFFFF',
  textMutedColor: '#64748B',  // --text-muted

  // Form inputs (search, controls).
  inputBg: '#FFFFFF',
  inputBorder: '#D9DFE6',
  inputTextColor: '#0F172A',
  inputBorderRadius: 4,

  // Brand color (selected sidebar row, active links).
  colorPrimary: '#2563EB',    // --primary
  colorSecondary: '#2563EB',

  // Typography. System stack so we don't have to ship web fonts to the
  // manager iframe; matches what the dashboard uses.
  fontBase: '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  fontCode: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
});

addons.setConfig({
  theme: slateDeveloperLight,
});
