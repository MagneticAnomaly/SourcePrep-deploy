import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { FolderTreePanel } from '../../components/project/FolderTreePanel';
import { sampleFileTree } from '../../components/project';
import type { ScopeSummary } from '../../types';

const meta: Meta<typeof FolderTreePanel> = {
  title: 'Dashboard/Widgets/FolderTreePanel',
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
  { id: 'global',    display_name: 'Global',    path_count: 247, assigned_to_role: null },
  { id: 'marketing', display_name: 'Marketing', path_count: 12,  assigned_to_role: null },
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
 * Panel showing a named "Marketing" scope with some paths already included.
 * The Edit button is visible because the active scope is not global.
 */
export const ScopePanelNamedPopulated: Story = {
  render: () => (
    <FolderTreePanel
      data={sampleFileTree}
      includedPaths={new Set(['websites/marketing/'])}
      scopes={SCOPE_GLOBAL_AND_MARKETING}
      activeScopeId="marketing"
      onSetActiveScope={() => {}}
      onCreateScope={async () => ({
        id: 'new', display_name: 'New', paths: [], assigned_to_role: null,
      })}
      onRenameScope={async () => {}}
      onDeleteScope={async () => {}}
      onToggleInclude={() => {}}
    />
  ),
  parameters: {
    docs: {
      description: {
        story: 'Named scope with included paths — the Edit (rename/delete) popover button is visible in the header.',
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
