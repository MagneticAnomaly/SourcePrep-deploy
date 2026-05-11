import type { StorybookConfig } from '@storybook/react-vite';
import { existsSync, mkdirSync, readdirSync } from 'fs';
import { tmpdir, homedir } from 'os';
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
  /(BugReportModal|EnterpriseAdminPanel|ConcurrencyHealth|CapacityHealth|RecentSwarmLogs|ProbeButton|PlanDropdown|SidebarPipelineQueue|RoadmapPanel|AuditPanel|OpportunitiesPanel|GraphEnrichmentPipeline|LogConsole|SwarmActivityPanel|SidebarAIGateway|AIModelsSettings|ProvenanceChip|RebuildDropdown|RebuildingRow|RecoverStagePanel|StageProgressBar|TraceCoveragePanel|GraphStructurePanel|TraceExplorer)\.stories\.[a-z]+$/;

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
  staticDirs: ['./static'],
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

    // Per-mode cache dir. dev.sh runs both private (port 6006) and public
    // (port 6007) Storybook dev servers from the same packages/ui workspace,
    // and the two instances have different `stories` lists — so they need
    // different pre-bundled deps. Without separate cache dirs they share
    // node_modules/.cache/sb-vite/, write conflicting chunks, and the surviving
    // server crashes seconds after a hot-reload with "Importing a module script
    // failed" 404s on chunk-XXXXX.js. Splitting the cache eliminates the
    // collision.
    //
    // The cache lives in $TMPDIR (or ~/.cache as fallback) instead of
    // node_modules/.cache/ because the repo may be on slow external storage
    // (USB drive on /Volumes/...). Vite's dep optimizer writes chunks then
    // immediately signals "ready" — on a slow drive the OS hasn't flushed the
    // file by the time the browser asks for it, producing "chunk-XXX.js does
    // not exist" 404s mid-session. Local SSD eliminates the FS-flush race.
    const projectSlug = isPublic ? 'public' : 'private';
    // Prefer ~/.cache (persists across reboots), fall back to $TMPDIR.
    const baseCacheRoot = join(homedir(), '.cache', 'codrag-sb-vite');
    try {
      if (!existsSync(baseCacheRoot)) {
        mkdirSync(baseCacheRoot, { recursive: true });
      }
      config.cacheDir = join(baseCacheRoot, projectSlug);
    } catch {
      config.cacheDir = join(tmpdir(), 'codrag-sb-vite', projectSlug);
    }

    // Splitting the cache dir means Vite pre-bundles each cache independently
    // and can produce two distinct React copies in the same JS context — which
    // breaks hooks with "null is not an object (evaluating
    // dispatcher.useContext)". `resolve.dedupe` forces React + React-DOM to
    // always resolve from a single node_modules path regardless of which
    // cache served them, restoring shared module identity for hooks.
    config.resolve = {
      ...(config.resolve ?? {}),
      dedupe: Array.from(
        new Set([
          ...((config.resolve?.dedupe as string[] | undefined) ?? []),
          'react',
          'react-dom',
          'react/jsx-runtime',
          '@storybook/blocks',
          '@storybook/react',
        ]),
      ),
    };

    // Expose STORYBOOK_PUBLIC to story modules so they can branch behavior
    // (e.g. FullDashboard hides devOnly panels in public mode but keeps them
    // in the local developer storybook). Vite's standard env-var prefix is
    // `VITE_*`; defining `import.meta.env.STORYBOOK_PUBLIC` explicitly avoids
    // having to rename the env var elsewhere in the build chain.
    config.define = {
      ...(config.define ?? {}),
      'import.meta.env.STORYBOOK_PUBLIC': JSON.stringify(isPublic),
    };

    // Tell Vite's dep optimizer to scan ALL story files upfront so it
    // pre-bundles every dep on startup. Without this, Vite discovers deps
    // lazily as you navigate between stories — when a heavy story (like
    // FullDashboard, which imports 30+ components) is opened, Vite kicks
    // off a fresh optimize pass, rewrites chunk hashes, and the browser's
    // in-memory module graph still references the old hashes. The result
    // is repeated "chunk-XXXXX.js does not exist" errors that require a
    // hard refresh. Pre-discovering all entries eliminates the race.
    config.optimizeDeps = {
      ...(config.optimizeDeps ?? {}),
      entries: [
        '.storybook/preview.tsx',
        'src/**/*.stories.@(ts|tsx|js|jsx|mdx)',
        'src/**/*.mdx',
      ],
      holdUntilCrawlEnd: true,
    };
    return config;
  },
};

export default config;
