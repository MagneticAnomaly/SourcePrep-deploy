import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { FolderTree, sampleFileTree, TreeNode } from '../../components/project';

const meta: Meta<typeof FolderTree> = {
  title: 'Dashboard/Widgets/FolderTree',
  component: FolderTree,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof FolderTree>;

export const Default: Story = {
  args: {
    data: sampleFileTree,
  },
};

export const Compact: Story = {
  args: {
    data: sampleFileTree,
    compact: true,
  },
};

export const RagInclusion: Story = {
  render: () => {
    // Initialize with paths that have indexed/pending status in the sample data
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(new Set([
      'src',
      'src/prep',
      'src/prep/server.py',
      'src/prep/cli.py',
      'src/prep/__init__.py',
      'src/prep/core',
      'src/prep/core/registry.py',
      'src/prep/core/embedding.py',
      'src/prep/core/trace.py',
      'src/prep/core/watcher.py',
      'src/prep/api',
      'src/prep/api/routes.py',
      'src/prep/api/auth.py',
      'docs',
      'docs/ARCHITECTURE.md',
      'docs/API.md',
      'docs/ROADMAP.md',
    ]));

    const handleToggleInclude = (paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const path of paths) {
          if (action === 'remove') {
            next.delete(path);
          } else {
            next.add(path);
          }
        }
        return next;
      });
    };

    return (
      <div className="space-y-4">
        <div className="p-3 bg-surface-raised rounded-lg border border-border">
          <div className="text-xs text-text-subtle mb-1">Folder Selection Behavior</div>
          <div className="text-sm text-text-muted space-y-1">
            <div>• <strong>Click folder row</strong> → selects/deselects ALL children recursively</div>
            <div>• <strong>Click arrow (▶)</strong> → only expands/collapses folder</div>
            <div>• <strong>Click file</strong> → toggles just that file</div>
            <div>• <span className="text-primary/60">Partial selection</span> = some children selected (folder stays bold)</div>
            <div>• <span className="text-text-subtle opacity-50">Ignored items</span> (like node_modules) cannot be selected</div>
          </div>
        </div>
        <div className="text-xs text-text-subtle">
          Included: {includedPaths.size} paths
        </div>
        <FolderTree
          data={sampleFileTree}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
        />
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story: `
**RAG Inclusion** is the primary functionality of the FolderTree.

**Status Flow:**
- **Unselected items**: No indicator - user hasn't added them to RAG
- **Selected → Pending**: Item is queued for indexing
- **Pending → Indexed**: Item has been processed, shows chunk count
- **Ignored**: Items like node_modules that cannot be selected

**Interaction:**
- Click anywhere on a row to toggle selection (not just the icon)
- Folders expand/collapse AND toggle selection on click
- Chevron button only toggles expand/collapse
- Ignored items have no hover state and cannot be clicked
        `,
      },
    },
  },
};

const simpleTree: TreeNode[] = [
  {
    name: 'project',
    type: 'folder',
    children: [
      { name: 'README.md', type: 'file', status: 'indexed', chunks: 5 },
      { name: 'package.json', type: 'file', status: 'indexed', chunks: 2 },
      {
        name: 'src',
        type: 'folder',
        children: [
          { name: 'index.ts', type: 'file', status: 'indexed', chunks: 10 },
          { name: 'utils.ts', type: 'file', status: 'pending' },
        ],
      },
    ],
  },
];

export const SimpleTree: Story = {
  args: {
    data: simpleTree,
  },
};

const statusShowcase: TreeNode[] = [
  {
    name: 'files',
    type: 'folder',
    children: [
      { name: 'indexed-file.py', type: 'file', status: 'indexed', chunks: 15 },
      { name: 'pending-file.py', type: 'file', status: 'pending', chunks: 0 },
      { name: 'ignored-file.py', type: 'file', status: 'ignored' },
      { name: 'error-file.py', type: 'file', status: 'error' },
    ],
  },
];

export const StatusShowcase: Story = {
  args: {
    data: statusShowcase,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows all possible file status states: indexed, pending, ignored, and error.',
      },
    },
  },
};

export const ContextWeighting: Story = {
  render: () => {
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(new Set([
      'src',
      'src/prep',
      'src/prep/server.py',
      'src/prep/cli.py',
      'src/prep/__init__.py',
      'src/prep/core',
      'src/prep/core/registry.py',
      'src/prep/core/embedding.py',
      'src/prep/core/trace.py',
      'src/prep/core/watcher.py',
      'src/prep/api',
      'src/prep/api/routes.py',
      'src/prep/api/auth.py',
      'docs',
      'docs/ARCHITECTURE.md',
      'docs/API.md',
      'docs/ROADMAP.md',
      'tests',
      'tests/test_registry.py',
      'tests/test_search.py',
      'tests/conftest.py',
    ]));

    // Pre-seed with example weights: docs de-emphasized, core boosted
    const [pathWeights, setPathWeights] = useState<Record<string, number>>({
      'docs': 0.5,
      'docs/ARCHITECTURE.md': 1.2,
      'src/prep/core': 1.5,
      'tests': 0.8,
    });

    const handleToggleInclude = (paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const p of paths) {
          if (action === 'remove') next.delete(p);
          else next.add(p);
        }
        return next;
      });
    };

    const handleWeightChange = (path: string, weight: number | null) => {
      setPathWeights((prev) => {
        const next = { ...prev };
        if (weight === null) {
          delete next[path];
        } else {
          next[path] = weight;
        }
        return next;
      });
    };

    return (
      <div className="space-y-4">
        <div className="p-3 bg-surface-raised rounded-lg border border-border">
          <div className="text-xs text-text-subtle mb-1">Context Weighting</div>
          <div className="text-sm text-text-muted space-y-1">
            <div>• <strong>Hover any row</strong> → weight badge appears (×1.0 default)</div>
            <div>• <strong>Click weight badge</strong> → edit weight (0.0–2.0)</div>
            <div>• <strong>Folder weight</strong> → propagates to all children (shown in <em>italic</em>)</div>
            <div>• <strong>Child override</strong> → overrides inherited weight (shown in normal text)</div>
            <div>• <span className="text-warning">Amber ×0.5</span> = de-emphasized, <span className="text-success">Green ×1.5</span> = boosted</div>
          </div>
        </div>
        <div className="text-xs text-text-subtle flex gap-4">
          <span>Included: {includedPaths.size} paths</span>
          <span>Weight overrides: {Object.keys(pathWeights).length}</span>
        </div>
        <FolderTree
          data={sampleFileTree}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
        />
        {Object.keys(pathWeights).length > 0 && (
          <div className="p-3 bg-surface-raised rounded-lg border border-border">
            <div className="text-xs text-text-subtle mb-1">Active Weight Overrides</div>
            <div className="font-mono text-xs text-text-muted space-y-0.5">
              {Object.entries(pathWeights).map(([p, w]) => (
                <div key={p}>{p}: ×{w.toFixed(1)}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story: `
**Context Weighting** lets users control how much influence each folder/file has in search results.

**Hierarchy:**
- Set weight on a folder → all children inherit it
- Override any child with its own weight
- Reset overrides to re-inherit from parent

**Weight scale:** 0.0 (excluded from results) to 2.0 (double importance). Default: 1.0.

**Use case:** De-emphasize large docs folders (×0.5) so they provide background context without dominating search results, while boosting core source code (×1.5).
        `,
      },
    },
  },
};

export const FullHeight: Story = {
  args: {
    data: sampleFileTree,
    className: 'h-[400px] overflow-y-auto',
  },
  decorators: [
    (Story) => (
      <div className="h-[500px] bg-gray-800 rounded-lg p-4">
        <div className="text-sm font-medium text-gray-300 mb-3">Project Files</div>
        <Story />
      </div>
    ),
  ],
};

const mergedScopeTree: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      { name: 'app.ts', type: 'file', status: 'indexed', chunks: 14 },
      { name: 'router.ts', type: 'file', status: 'indexed', chunks: 9 },
      { name: 'legacy.ts', type: 'file' },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      { name: 'e2e.spec.ts', type: 'file' },
      { name: 'unit.spec.ts', type: 'file' },
    ],
  },
  // Files that match always-ignored globs — rendered with strikethrough,
  // no include/exclude toggles.
  { name: 'AGENTS.md', type: 'file' },
  { name: 'CLAUDE.md', type: 'file' },
  { name: '.cursorrules', type: 'file' },
];

const alwaysIgnored = [
  '**/AGENTS.md',
  '**/CLAUDE.md',
  '**/GEMINI.md',
  '**/.cursorrules',
  '**/.cursor/rules/*.mdc',
];

export const MergedScope: Story = {
  render: () => {
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(new Set(['src', 'src/app.ts', 'src/router.ts']));
    const [excludedPaths, setExcludedPaths] = useState<Set<string>>(new Set(['tests']));

    const toggleInclude = (paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const p of paths) (action === 'add' ? next.add(p) : next.delete(p));
        return next;
      });
    };
    const toggleExclude = (paths: string[], action: 'add' | 'remove') => {
      setExcludedPaths((prev) => {
        const next = new Set(prev);
        for (const p of paths) (action === 'add' ? next.add(p) : next.delete(p));
        return next;
      });
    };

    return (
      <div className="space-y-4 max-w-xl">
        <div className="p-3 bg-surface-raised rounded-lg border border-border">
          <div className="text-xs text-text-subtle mb-1">Merged Scope Tree (Phase 98)</div>
          <div className="text-sm text-text-muted space-y-1">
            <div>• <strong>☑ Include checkbox</strong> (primary) — adds to RAG knowledge</div>
            <div>• <strong>🚫 Exclude icon</strong> (error/red) — removes from trace + knowledge</div>
            <div>• Checking one auto-unchecks the other (mutual exclusion)</div>
            <div>• <span className="line-through text-text-subtle">AGENTS.md / CLAUDE.md</span> — always-ignored, not toggleable</div>
            <div>• Row click = expand/collapse (folders) or no-op (files in panel variant)</div>
          </div>
        </div>
        <div className="text-xs text-text-subtle flex gap-4">
          <span>{includedPaths.size} included</span>
          <span className="text-error">{excludedPaths.size} excluded</span>
        </div>
        <FolderTree
          data={mergedScopeTree}
          includedPaths={includedPaths}
          onToggleInclude={toggleInclude}
          excludedPaths={excludedPaths}
          onToggleExclude={toggleExclude}
          alwaysIgnoredPatterns={alwaysIgnored}
        />
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story: `
**Merged Scope Tree** demonstrates the four row states after the include/exclude unification:

| State | Include | Exclude | Name |
|-------|---------|---------|------|
| **Default** | ☐ | ☐ | normal |
| **Included** | ☑ | ☐ | **bold**, primary tint |
| **Excluded** | ☐ | 🚫 | ~~strikethrough~~ red tint |
| **Always-ignored** | — | — | ~~strikethrough~~ subtle |

Mutual exclusion is enforced in the component: checking include on an excluded path auto-un-excludes, and vice versa.
        `,
      },
    },
  },
};
