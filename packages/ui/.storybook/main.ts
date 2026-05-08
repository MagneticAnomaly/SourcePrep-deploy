import type { StorybookConfig } from '@storybook/react-vite';
import { readdirSync } from 'fs';
import { join } from 'path';

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
//   2. Mock data or component JSDoc contains internal roadmap / debt / phase
//      content that would render on screen or surface in the Controls panel
//      even with autodocs disabled. These need a mock-data + JSDoc sweep
//      (see docs/Phase131_StorybookCuration §5.2) before going public.
const internalStoryFilter =
  /(BugReportModal|EnterpriseAdminPanel|ConcurrencyHealth|CapacityHealth|RecentSwarmLogs|ProbeButton|PlanDropdown|SidebarPipelineQueue|RoadmapPanel|AuditPanel|OpportunitiesPanel|GraphEnrichmentPipeline|LogConsole|SwarmActivityPanel|SidebarAIGateway|AIModelsSettings|ProvenanceChip)\.stories\.[a-z]+$/;

// Walk packages/ui/src/ for *.mdx and *.stories.{js,jsx,mjs,ts,tsx}. Storybook
// CLI invokes main.ts with cwd=packages/ui. We can't use __dirname (the package
// is ESM), and we keep this dependency-free to avoid CJS/ESM interop quirks
// with fast-glob.
const STORY_FILE_RE = /\.(stories\.(js|jsx|mjs|ts|tsx)|mdx)$/;

function walkStories(dir: string, results: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walkStories(full, results);
    else if (STORY_FILE_RE.test(entry.name)) results.push(full);
  }
  return results;
}

function resolveStories(): string[] {
  const all = walkStories('src');
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
