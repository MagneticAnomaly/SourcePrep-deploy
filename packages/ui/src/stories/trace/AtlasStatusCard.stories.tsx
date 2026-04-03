import type { Meta, StoryObj } from '@storybook/react';
import { AtlasStatusCard } from '../../components/trace/AtlasStatusCard';
import type { AtlasStatus } from '../../types';

const meta: Meta<typeof AtlasStatusCard> = {
  title: 'Trace/AtlasStatusCard',
  component: AtlasStatusCard,
  parameters: {
    layout: 'padded',
    docs: { description: { component: 'Codebase Atlas status card showing generation status, stats (chars, modules, files), and a collapsible content preview. The Atlas is the structural brain of CoDRAG — a compressed representation of your entire codebase architecture.' } },
  },
};

export default meta;
type Story = StoryObj<typeof AtlasStatusCard>;

const freshAtlas: AtlasStatus = {
  exists: true,
  content: `IDENTITY: A local-first AI coding assistant with MCP integration, featuring a VS Code extension, React dashboard, and shared UI component library.

STACK: TypeScript, React, Python, Rust, Tauri. Build tools include Storybook for design system documentation and standard tooling for VS Code extension packaging. 1143 files across 5085 graph nodes with 21767 edges.

WORKSPACE MAP:
_root (842 files): MCP, marketing, UI foundations, local-first architecture, security
packages/ui (230 files): UI component library, Storybook design system, dashboard primitives
src/codrag/dashboard (37 files): Dashboard application with React hooks and state management
packages/vscode (20 files): VS Code extension with daemon integration

CROSS-CUTTING: Shared domains are ui, dashboard, and vscode-extension. Five hub files drive cross-segment connectivity.`,
  mode: 'llm',
  model: 'claude-sonnet-4-20250514',
  generated_at: new Date(Date.now() - 3600000).toISOString(),
  file_count: 1143,
  module_count: 17,
  char_count: 4850,
  stale: false,
};

/** Fresh Atlas — recently generated with full content */
export const Fresh: Story = {
  args: { atlas: freshAtlas },
};

/** Stale Atlas — needs rebuild */
export const Stale: Story = {
  args: {
    atlas: { ...freshAtlas, stale: true, generated_at: new Date(Date.now() - 86400000 * 3).toISOString() },
  },
};

/** Not Generated — atlas hasn't been created yet */
export const NotGenerated: Story = {
  args: { atlas: { exists: false, content: null } },
};

/** Structural mode — no LLM, auto-generated from graph */
export const Structural: Story = {
  args: {
    atlas: { ...freshAtlas, mode: 'structural', model: 'structural', char_count: 2200 },
  },
};
