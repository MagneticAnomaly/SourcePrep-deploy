import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { FolderTreePanel } from '../../components/project/FolderTreePanel';
import { sampleFileTree } from '../../components/project';
import type { TreeNode } from '../../components/project/FolderTree';
import type { ScopeSummary } from '../../types';

// ── Small, mixed-state tree for the canonical "Knowledge Scope" story.
// Deliberately low chunk counts so the docs-site embed models a tight,
// focused scope rather than an "index everything" posture.
const KNOWLEDGE_SCOPE_TREE: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'auth',
        type: 'folder',
        children: [
          { name: 'login.py',     type: 'file', status: 'indexed', chunks: 4 },
          { name: 'jwt.py',       type: 'file', status: 'indexed', chunks: 6 },
          { name: 'session.py',   type: 'file', status: 'pending' },
        ],
      },
      {
        name: 'middleware',
        type: 'folder',
        children: [
          { name: 'rate_limit.py', type: 'file', status: 'indexed', chunks: 3 },
          { name: 'cors.py',       type: 'file', status: 'pending' },
        ],
      },
    ],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [
      { name: 'AUTH.md',      type: 'file', status: 'indexed', chunks: 5 },
      { name: 'INTERNAL.md',  type: 'file', status: 'ignored' },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      { name: 'test_auth.py', type: 'file' },
    ],
  },
];

const meta: Meta<typeof FolderTreePanel> = {
  title: 'Dashboard/Project/FolderTreePanel',
  component: FolderTreePanel,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FolderTreePanel>;

// ── Scope fixtures ────────────────────────────────────────────────────────────

const SCOPE_GLOBAL_AND_MARKETING: ScopeSummary[] = [
  { id: 'global',    display_name: 'Global',    path_count: 13, assigned_to_role: null },
  { id: 'marketing', display_name: 'Marketing', path_count: 4,  assigned_to_role: null },
];

const SCOPE_GLOBAL_AND_AUTH: ScopeSummary[] = [
  { id: 'global',       display_name: 'Global',       path_count: 13, assigned_to_role: null },
  { id: 'auth-feature', display_name: 'auth-feature', path_count: 6,  assigned_to_role: null },
];

const SCOPE_TRIO: ScopeSummary[] = [
  { id: 'global',        display_name: 'Global',        path_count: 247, assigned_to_role: null },
  { id: 'marketing',     display_name: 'Marketing',     path_count: 12,  assigned_to_role: null },
  { id: 'data_cleaning', display_name: 'Data Cleaning', path_count: 34,  assigned_to_role: null },
];

// ── Stories ───────────────────────────────────────────────────────────────────

/**
 * Panel showing the Global scope (default). The scope dropdown is visible with
 * two scopes; since the active scope is "global", the Edit button is hidden
 * (global scope cannot be renamed or deleted).
 */
export const ScopePanelGlobal: Story = {
  render: () => (
    <FolderTreePanel
      data={sampleFileTree}
      includedPaths={new Set(['src/'])}
      scopes={SCOPE_GLOBAL_AND_MARKETING}
      activeScopeId="global"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
      bare
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'Global scope active — Edit popover is hidden because global scope cannot be renamed or deleted.',
      },
    },
  },
};

/**
 * Canonical "Knowledge Scope" story for docs-site embedding.
 * Small, focused tree showing mixed file states:
 *   - src/auth/ and src/middleware/ are in scope (indexed + pending)
 *   - docs/AUTH.md is in scope and indexed
 *   - docs/INTERNAL.md is explicitly excluded
 *   - tests/ is out of scope (no status)
 * Numbers kept deliberately low to model a tight working scope.
 */
export const ScopePanelNamedPopulated: Story = {
  render: () => (
    <FolderTreePanel
      data={KNOWLEDGE_SCOPE_TREE}
      includedPaths={new Set(['src/auth', 'src/middleware', 'docs/AUTH.md'])}
      excludedPaths={new Set(['docs/INTERNAL.md'])}
      scopes={SCOPE_GLOBAL_AND_AUTH}
      activeScopeId="auth-feature"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
      onToggleExclude={() => {}}
      bare
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'A tight, named scope ("auth-feature") with mixed file states — some indexed, some pending, one explicitly excluded. The Edit (rename/delete) popover is visible because the active scope is not Global.',
      },
    },
  },
};

/**
 * Freshly-created named scope with zero paths. The empty-state banner
 * ("This scope is empty. Click files and folders to add them.") should appear.
 */
export const ScopePanelEmpty: Story = {
  render: () => (
    <FolderTreePanel
      data={sampleFileTree}
      includedPaths={new Set()}
      scopes={[
        { id: 'global',        display_name: 'Global',        path_count: 247, assigned_to_role: null },
        { id: 'data_cleaning', display_name: 'Data Cleaning', path_count: 0,   assigned_to_role: null },
      ]}
      activeScopeId="data_cleaning"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
      bare
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'Named scope with no paths yet — empty-state banner prompts the user to add files/folders.',
      },
    },
  },
};

/**
 * The "+" (add scope) button is part of the scope header. This story shows the
 * panel in a state where the user has clicked "+" and the inline create input
 * is visible. Because FolderTreePanel manages `showCreate` internally, we use
 * a stateful wrapper so the reviewer can interact with the actual flow rather
 * than a frozen snapshot.
 */
export const ScopePanelCreateInputOpen: Story = {
  render: () => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [scopes, setScopes] = useState(SCOPE_TRIO);
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [activeScopeId, setActiveScopeId] = useState('global');

    return (
      <div className="space-y-3">
        <p className="text-xs text-text-subtle">
          Click the <strong>+</strong> button in the scope header to open the inline create input.
        </p>
        <FolderTreePanel
          data={sampleFileTree}
          scopes={scopes}
          activeScopeId={activeScopeId}
          onSetActiveScope={setActiveScopeId}
          onCreateScope={async (name) => {
            const newScope = {
              id: name.toLowerCase().replace(/\s+/g, '_'),
              display_name: name,
              paths: [],
              assigned_to_role: null,
            };
            setScopes(prev => [...prev, { ...newScope, path_count: 0 }]);
            setActiveScopeId(newScope.id);
            return newScope;
          }}
          onRenameScope={async () => {}}
          onDeleteScope={async () => {}}
          onToggleInclude={() => {}}
          bare
        />
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive story — click "+" in the scope header to open the inline name input and create a new scope. The new scope is appended to the dropdown.',
      },
    },
  },
};

/**
 * Demonstrates path weights — the small ×N.N controls per file/folder.
 *
 * Weight visuals (from FolderTree.tsx:380-389):
 *   • ×N.N > 1.0   → green tint (boost)
 *   • ×N.N < 1.0   → amber tint (suppress)
 *   • ×1.0         → faded text (default)
 *   • italic       → inherited from a parent folder
 *
 * This fixture sets explicit weights on src/core (1.5), src/utils (0.7),
 * tests (0.3), and docs/README.md (1.8), so the embedded preview on the
 * Path Weights docs page shows every state at once — including inherited
 * children (src/core/auth.py inherits ×1.5 from its parent folder, etc.).
 */
const PATH_WEIGHTS_TREE: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'core',
        type: 'folder',
        children: [
          { name: 'auth.py',    type: 'file', status: 'indexed', chunks: 6 },
          { name: 'billing.py', type: 'file', status: 'indexed', chunks: 4 },
        ],
      },
      {
        name: 'utils',
        type: 'folder',
        children: [
          { name: 'helpers.py', type: 'file', status: 'indexed', chunks: 3 },
          { name: 'logging.py', type: 'file', status: 'indexed', chunks: 2 },
        ],
      },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      { name: 'test_auth.py', type: 'file', status: 'indexed', chunks: 5 },
    ],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [
      { name: 'README.md', type: 'file', status: 'indexed', chunks: 4 },
    ],
  },
];

export const ScopePanelWithPathWeights: Story = {
  render: () => (
    <FolderTreePanel
      data={PATH_WEIGHTS_TREE}
      // Specific-file includes (not whole folders) — matches a realistic working scope.
      // Per FolderTree.tsx:557, included rows get a faint bg-primary/5 tint; only the
      // included files here will tint, not every descendant.
      includedPaths={new Set([
        'src/core/auth.py',
        'src/core/billing.py',
        'src/utils/helpers.py',
        'tests/test_auth.py',
        'docs/README.md',
      ])}
      pathWeights={{
        'src/core':         1.5,
        'src/utils':        0.7,
        'tests':            0.3,
        'docs/README.md':   1.8,
      }}
      onWeightChange={() => {}}
      onToggleInclude={() => {}}
      excludedPaths={new Set()}
      onToggleExclude={() => {}}
      bare
      scopes={[
        { id: 'global', display_name: 'Global', path_count: 5, assigned_to_role: null },
      ]}
      activeScopeId="global"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'Path weights demo — green ×N.N for boosts (>1.0), amber for suppressions (<1.0), faded ×1.0 for default, italic for weights inherited from a parent folder.',
      },
    },
  },
};

/**
 * Named scope with both includedPaths and excludedPaths set. The exclude
 * controls should be read-only (disabled) because the active scope is a named
 * scope (not global), so the tree renders with `scopeReadOnlyExclude=true`.
 */
export const ScopePanelExcludeDisabled: Story = {
  render: () => (
    <FolderTreePanel
      data={sampleFileTree}
      includedPaths={new Set(['websites/marketing/'])}
      excludedPaths={new Set(['vendor/'])}
      scopes={SCOPE_GLOBAL_AND_MARKETING}
      activeScopeId="marketing"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
      bare
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'Named scope with an excluded path — exclude toggles are read-only (scopeReadOnlyExclude=true) because only the global scope can manage exclusions.',
      },
    },
  },
};
