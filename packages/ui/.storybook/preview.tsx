import type { Preview } from '@storybook/react';
import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Hammer, Zap, Settings, Eye, FolderTree, BarChart3 } from 'lucide-react';
import '../src/styles/index.css';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { PanelChrome } from '../src/components/layout/PanelChrome';
import { PANEL_REGISTRY } from '../src/config/panelRegistry';
import type { PanelDefinition } from '../src/config/panelRegistry';

// ────────────────────────────────────────────────────────────────────────────
// Panel-chrome wrapping
//
// When a story renders a top-level dashboard panel, we wrap it in PanelChrome
// (the same drag-handle + title bar + collapse/close header that the Tauri
// dashboard uses) so visitors see the panel as it actually appears in the
// product. Sub-components (status badges, list rows, sub-cards) are NOT
// wrapped — they're shown bare and laid out via `pickLayout` below.
//
// Two ways a story is recognised as a panel:
//   1. A registry entry — uses the canonical PanelDefinition from
//      packages/ui/src/config/panelRegistry.ts (title/icon/description/docsUrl).
//   2. An inline override — for stories whose component is a panel in the
//      product but doesn't (yet) have a registry entry of its own.
// ────────────────────────────────────────────────────────────────────────────

type InlinePanelSpec = { title: string; icon: LucideIcon; description?: string };
type PanelSpec = string | InlinePanelSpec;

const STORY_PANELS: Record<string, PanelSpec> = {
  // Registry-backed entries (canonical title/icon/description from PANEL_REGISTRY)
  'Dashboard/Search/SearchPanel': 'search',
  'Dashboard/Search/ContextOutput': 'context-output',
  'Dashboard/Index/IndexStatusCard': 'status',
  'Dashboard/Index/UsageGuidePanel': 'usage-guide',
  'Dashboard/Project/FolderTreePanel': 'file-tree',
  'Dashboard/Trace/AtlasLensPanel': 'atlas',
  'Dashboard/Trace/Graph': 'trace',
  'Dashboard/Trace/GraphStructurePanel': 'graph-structure',
  'Dashboard/Visualization/ActivityHeatmap': 'activity-heatmap',
  'Dashboard/LLM/LLMStatusWidget': 'llm-status',
  'Dashboard/Agents/AgentOpsPanel': 'agent-ops',
  'Dashboard/Console/LogConsole': 'log-console',
  'Dashboard/Audit/AuditPanel': 'audit',
  'Dashboard/Audit/OpportunitiesPanel': 'opportunities',
  'Dashboard/Roadmap/RoadmapPanel': 'roadmap',
  'Dashboard/Pipeline/GraphEnrichmentPipeline': 'trace-pipeline',

  // Inline (no canonical registry entry — these are panels in the product UI
  // but represented differently in the modular layout config).
  'Dashboard/Build/BuildCard': { title: 'Build', icon: Hammer },
  'Dashboard/LLM/EndpointManager': { title: 'LLM Endpoints', icon: Zap },
  'Dashboard/LLM/AdvancedLLMSettings': { title: 'Advanced LLM', icon: Settings },
  'Dashboard/LLM/DeepAnalysisSettings': { title: 'Deep Analysis', icon: Settings },
  'Dashboard/Project/ProjectSettingsPanel': { title: 'Project Settings', icon: Settings },
  'Dashboard/Watch/WatchControls': { title: 'File Watch', icon: Eye },
  'Dashboard/Index/IndexStats': { title: 'Index Stats', icon: BarChart3 },
  'Dashboard/Project/FolderTree': { title: 'Project Files', icon: FolderTree },
};

function resolvePanel(title: string): InlinePanelSpec | null {
  const spec = STORY_PANELS[title];
  if (!spec) return null;
  if (typeof spec === 'string') {
    const def: PanelDefinition | undefined = PANEL_REGISTRY.find((p) => p.id === spec);
    if (!def) return null;
    return { title: def.title, icon: def.icon, description: def.description };
  }
  return spec;
}

// ────────────────────────────────────────────────────────────────────────────
// Layout resolver
//
// `parameters.layout = 'fullscreen'` is the global Storybook canvas — no
// padding, no centering. Per section we render the story inside a different
// container so primitives don't get cramped in the top-left and marketing
// heroes still go edge-to-edge like they do on the live site.
// ────────────────────────────────────────────────────────────────────────────

type LayoutKind = 'fullscreen' | 'centered' | 'padded' | 'modal-backdrop';

function pickLayout(title: string): LayoutKind {
  // Real fullscreen surfaces — render with no extra wrapper.
  if (title.startsWith('Dashboard/Layouts/')) return 'fullscreen';
  if (title.startsWith('Website/Layout/')) return 'fullscreen';
  if (title === 'Website/Marketing/Hero') return 'fullscreen';
  if (title === 'Website/Marketing/FeatureBlocks') return 'fullscreen';

  // Modals — centered, dimmed backdrop.
  if (title.startsWith('Modals/')) return 'modal-backdrop';

  // Marketing demos — centered with a working canvas around them.
  if (title.startsWith('Website/Demos/')) return 'centered';

  // Long-form / specimen content.
  if (title.startsWith('Foundations/')) return 'padded';
  if (title.startsWith('Patterns/')) return 'padded';
  if (title.startsWith('Website/Marketing/Research/')) return 'padded';
  if (title.startsWith('Website/')) return 'padded';

  // Primitives → centered with breathing room.
  if (title.startsWith('Primitives/')) return 'centered';

  // Dashboard panels (chromed) → padded canvas around them.
  // Dashboard sub-components (no chrome) → centered.
  if (title.startsWith('Dashboard/')) {
    return STORY_PANELS[title] ? 'padded' : 'centered';
  }

  return 'fullscreen';
}

function LayoutWrapper({
  layout,
  children,
}: {
  layout: LayoutKind;
  children: React.ReactNode;
}) {
  const base = 'min-h-screen w-full bg-background text-foreground font-sans transition-colors duration-200';
  switch (layout) {
    case 'fullscreen':
      return <div className={base}>{children}</div>;
    case 'centered':
      return <div className={`${base} flex items-center justify-center p-12`}>{children}</div>;
    case 'padded':
      return <div className={`${base} mx-auto max-w-5xl p-8`}>{children}</div>;
    case 'modal-backdrop':
      return (
        <div className={`${base} flex items-center justify-center p-8`} style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          {children}
        </div>
      );
  }
}

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      disable: true,
    },
    layout: 'fullscreen',
    options: {
      // Phase 131: design-system reading order — start with the foundations,
      // build up to atoms (Primitives), then composed atoms (Patterns), then
      // full product surfaces. Within each top-level, items are nested in a
      // task-oriented sequence; everything not listed falls back to alpha.
      storySort: {
        method: 'alphabetical',
        order: [
          'Foundations',
          ['Introduction', 'Accessibility', 'Visual Directions', 'Tokens',
            ['Colors', 'Typography', 'Spacing']],
          'Primitives',
          'Patterns',
          'Modals',
          'Dashboard',
          ['Introduction', 'Layouts', '*'],
          'Website',
          ['Layout', 'Marketing', 'Demos', 'Research'],
        ],
      },
    },
  },
  globalTypes: {
    theme: {
      name: 'Mode',
      description: 'Light/Dark mode',
      defaultValue: 'dark',
      toolbar: {
        icon: 'circlehollow',
        items: [
          { value: 'light', icon: 'sun', title: 'Light' },
          { value: 'dark', icon: 'moon', title: 'Dark' },
        ],
        showName: true,
      },
    },
    prepTheme: {
      name: 'Visual Style',
      description: 'Prep visual theme direction',
      // Phase 131: default to Slate Developer ('a') so the public storybook
      // boots into a clean, IDE-aligned aesthetic. Pairs with the light
      // Slate Developer manager chrome defined in manager.ts. Visitors can
      // still flip themes via this toolbar. Supersedes Phase 13's earlier
      // Retro-Futurism default.
      defaultValue: 'a',
      toolbar: {
        icon: 'paintbrush',
        items: [
          { value: 'none', title: 'Default (Tokens only)' },
          { value: 'a', title: 'A: Slate Developer' },
          { value: 'b', title: 'B: Deep Focus' },
          { value: 'c', title: 'C: Signal Green' },
          { value: 'd', title: 'D: Warm Craft' },
          { value: 'e', title: 'E: Neo-Brutalist' },
          { value: 'f', title: 'F: Swiss Minimal' },
          { value: 'g', title: 'G: Glass-Morphic' },
          { value: 'h', title: 'H: Retro-Futurism' },
          { value: 'm', title: 'M: Retro Aurora' },
          { value: 'n', title: 'N: Retro Mirage' },
          { value: 'i', title: 'I: Studio Collage' },
          { value: 'j', title: 'J: Yale Grid' },
          { value: 'k', title: 'K: Inclusive Focus' },
          { value: 'l', title: 'L: Enterprise Console' },
        ],
        showName: true,
      },
    },
    docsMode: {
      name: 'Docs Mode',
      description: 'Reserved for embedded docs-site previews via StoryEmbed',
      defaultValue: 'false',
      toolbar: {
        icon: 'eye',
        items: [
          { value: 'false', title: 'Dev Mode' },
          { value: 'true', title: 'Docs Mode (clean)' },
        ],
      },
    },
  },
  decorators: [
    (Story, context) => {
      const mode = context.globals.theme;
      const prepTheme = context.globals.prepTheme;
      const title = (context.title as string) || '';
      const layout = pickLayout(title);
      const panel = resolvePanel(title);

      React.useEffect(() => {
        document.documentElement.classList.toggle('dark', mode === 'dark');
        document.documentElement.setAttribute('data-theme', mode);
        if (prepTheme && prepTheme !== 'none') {
          document.documentElement.setAttribute('data-prep-theme', prepTheme);
        } else {
          document.documentElement.removeAttribute('data-prep-theme');
        }
      }, [mode, prepTheme]);

      const body = panel ? (
        <PanelChrome title={panel.title} icon={panel.icon} description={panel.description}>
          <Story />
        </PanelChrome>
      ) : (
        <Story />
      );

      return <LayoutWrapper layout={layout}>{body}</LayoutWrapper>;
    },
  ],
};

export default preview;
