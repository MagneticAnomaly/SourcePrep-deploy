import type { StorybookConfig } from '@storybook/react-vite';
import { sync as glob } from 'fast-glob';
import { resolve } from 'path';

// Public-deploy mode: when STORYBOOK_PUBLIC=true the bundle is hardened for
// publishing at storybook.sourceprep.io — autodocs is disabled (no Show-code
// reveal, no ArgTypes table) and internal-only stories are excluded.
// See docs/Phase131_StorybookCuration/00_curation_plan.md for the full split.
const isPublic = process.env.STORYBOOK_PUBLIC === 'true';

// Files matching this regex are excluded from the public build. Match against
// the story file path. Add new entries here, not via story-glob negation —
// Storybook's `stories` array does not honor `!`-prefixed patterns.
//
// Two reasons a story lands here:
//   1. Internal-only surface (admin, dev diagnostics, internal-flow modals).
//   2. Mock data contains internal roadmap / debt / phase content that would
//      render on screen even with autodocs disabled. These need a mock-data
//      sweep (see docs/Phase131_StorybookCuration §5.2) before going public.
const internalStoryFilter =
  /(BugReportModal|EnterpriseAdminPanel|ConcurrencyHealth|CapacityHealth|RecentSwarmLogs|ProbeButton|PlanDropdown|SidebarPipelineQueue|RoadmapPanel|AuditPanel|OpportunitiesPanel|GraphEnrichmentPipeline|LogConsole)\.stories\.[a-z]+$/;

function resolveStories(): string[] {
  const cwd = resolve(__dirname, '..');
  const patterns = ['src/**/*.mdx', 'src/**/*.stories.@(js|jsx|mjs|ts|tsx)'];
  const all = glob(patterns, { cwd, absolute: false });
  const filtered = isPublic ? all.filter((p) => !internalStoryFilter.test(p)) : all;
  // Storybook expects paths relative to the .storybook directory.
  return filtered.map((p) => `../${p}`);
}

const config: StorybookConfig = {
  stories: resolveStories(),
  addons: [
    '@storybook/addon-links',
    '@storybook/addon-essentials',
    '@storybook/addon-interactions',
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: isPublic ? false : 'tag',
  },
  viteFinal: async (config) => {
    // vite-plugin-dts emits .d.ts files into the Vite outDir, which during
    // `storybook build` is `storybook-static/` — leaking the full @prep/ui
    // type surface (including the ApiClient interface) into the public bundle.
    // Strip it from the Storybook build only; the library build (npm run build)
    // still emits declarations to `dist/`.
    config.plugins = (config.plugins ?? []).filter((plugin) => {
      if (!plugin || Array.isArray(plugin)) return true;
      const name = (plugin as { name?: string }).name;
      return name !== 'vite:dts';
    });
    return config;
  },
};

export default config;
