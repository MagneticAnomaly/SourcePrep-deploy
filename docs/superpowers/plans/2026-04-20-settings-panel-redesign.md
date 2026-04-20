# Settings Panel Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cramped right-edge Settings drawer with a full-screen overlay that uses a left nav, hard-separates project-scope from global-scope controls, and gates Developer settings out of production builds.

**Architecture:** Portal-rendered full-screen overlay with a 240px left rail and three scope-labelled nav groups (`PROJECT · <name>`, `GLOBAL`, `DEVELOPER`). All pages use a shared `SettingsPage` wrapper with a scope chip. Global pages autosave; Project pages keep today's dirty-flag + explicit Save pattern. The overlay sits behind a `settings_overlay_v2` feature flag during rollout and replaces `SettingsDrawer.tsx` / `AdvancedSettingsPanel.tsx` at the end. No backend, AI Gateway, Pipeline Queue, or dashboard panels are touched.

**Tech Stack:** React 18, TypeScript (strict), Vite 4, Tailwind with `@codrag/ui` design tokens, Vitest for pure-logic tests, Storybook for visual verification.

**Testing approach:** The UI package has no DOM test infrastructure (no `@testing-library/react`). Per the existing `HealthBadge.test.tsx` pattern, tests are **pure-logic vitest** (no render) plus **Storybook stories** for visual verification. Component behavior is manually verified via `scripts/dev.sh`.

**Reference documents:**
- Spec: `docs/superpowers/specs/2026-04-20-settings-panel-redesign-design.md`
- Today's drawer: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx` (803 LoC)
- Today's advanced panel: `src/codrag/dashboard/src/components/settings/AdvancedSettingsPanel.tsx` (380 LoC)
- Pattern reference for pure-logic tests: `packages/ui/src/components/pipeline/__tests__/HealthBadge.test.tsx`

**Commit convention:** `feat(settings-v2): ...`, `refactor(settings-v2): ...`, `test(settings-v2): ...`. No Co-Authored-By trailer.

---

## File Structure

### New files

**Shared primitives (`packages/ui`)**
- `packages/ui/src/components/settings/SettingRow.tsx` — label + description + control row.
- `packages/ui/src/components/settings/Section.tsx` — optional-titled group within a page.
- `packages/ui/src/components/settings/scope.ts` — pure helpers: `scopeChipLabel(scope)`, `scopeAriaLabel(scope)`.
- `packages/ui/src/components/settings/__tests__/scope.test.ts` — pure-logic test.
- `packages/ui/src/components/settings/__tests__/SettingRow.stories.tsx` — Storybook.
- `packages/ui/src/components/settings/__tests__/Section.stories.tsx` — Storybook.
- `packages/ui/src/components/settings/index.ts` — barrel export.

**Dashboard settings v2 (`src/codrag/dashboard/src/components/settings/v2`)**
- `SettingsOverlay.tsx` — top-level portal, top bar, routing, layout.
- `SettingsNav.tsx` — left rail with three groups.
- `SettingsPage.tsx` — page wrapper (header, scope chip, save area, body).
- `useSettingsRoute.ts` — reads/writes `?settings=<page>` param.
- `useSettingsDirty.ts` — dirty flag + leave guard hook.
- `devGate.ts` — `isDevBuild()` + route-filter helper.
- `routeParser.ts` — pure URL param parser (extractable for unit tests).
- `pages/Sources.tsx`
- `pages/TraceIndexing.tsx`
- `pages/DeepAnalysis.tsx`
- `pages/DangerZone.tsx`
- `pages/Appearance.tsx`
- `pages/ChunkingEmbeddings.tsx`
- `pages/PipelineDefaults.tsx`
- `pages/License.tsx`
- `pages/Integrations.tsx`
- `pages/DevToggles.tsx`
- `pages/Diagnostics.tsx`
- `pages/SelectiveReset.tsx`
- `__tests__/routeParser.test.ts`
- `__tests__/devGate.test.ts`
- `__tests__/dirty.test.ts`

### Modified files
- `src/codrag/dashboard/src/App.tsx` — replace drawer mount with overlay mount behind flag; wire `⌘,` shortcut; wire feature flag read.
- `packages/ui/src/index.ts` — export new settings primitives.
- `packages/ui/vite.config.ts` — add `settings` to the externalizable subpaths list only if needed (likely not — internal imports).

### Deleted files (at end of rollout)
- `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`
- `src/codrag/dashboard/src/components/settings/AdvancedSettingsPanel.tsx`

---

## Lift Template

Several tasks "lift" pre-existing JSX out of `SettingsDrawer.tsx` or `AdvancedSettingsPanel.tsx` into a new page component. Every lift task follows this template:

```tsx
// src/codrag/dashboard/src/components/settings/v2/pages/<Name>.tsx
import { SettingsPage, SettingRow, Section } from '@codrag/ui';
import type { ProjectConfig, GlobalConfig } from '...types';

interface <Name>PageProps {
  /* props the lifted JSX already reads in SettingsDrawer */
  /* plus a save/dirty pair for Project pages */
}

export function <Name>Page(props: <Name>PageProps) {
  return (
    <SettingsPage
      title="<Human title>"
      scope="project" | "global" | "developer"
      description="<one-line description>"
      actions={/* <SaveButton/> for project pages, undefined otherwise */}
    >
      <Section>
        {/* lifted JSX, rewrapped in <SettingRow label=… description=… control=…/> */}
      </Section>
    </SettingsPage>
  );
}
```

**Rewrap rule:** Every form control in the lifted JSX must end up inside a `<SettingRow>` whose `label` and `description` match the text currently rendered beside or above that control. Do **not** invent new copy — preserve the exact labels and help text from the drawer. This keeps the lift purely structural and avoids scope creep.

**Scope-split rule:** If the source tab (e.g., old "Advanced") contained controls from multiple scopes, each control goes into the new page that matches its scope. Per-project trace limits land in `TraceIndexing.tsx`; global chunking lands in `ChunkingEmbeddings.tsx`; etc. Never copy the "Advanced" tab wholesale.

**Manual verification per lift:** Open `?settings=<page>`, visually confirm every control from the old tab is present with the same label, help text, and initial value. Save (project) or change-and-reload (global) and confirm persistence.

---

## Task Order

Tasks 1–9 build foundation (primitives, shell, flag). Tasks 10–22 migrate pages. Task 23 flips the flag. Task 24 deletes the old drawer and cleans up.

---

## Task 1: Pure scope helpers and test

**Files:**
- Create: `packages/ui/src/components/settings/scope.ts`
- Test: `packages/ui/src/components/settings/__tests__/scope.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// packages/ui/src/components/settings/__tests__/scope.test.ts
import { describe, it, expect } from 'vitest';
import { scopeChipLabel, scopeAriaLabel } from '../scope';

describe('scopeChipLabel', () => {
  it('returns "Project" for project', () => {
    expect(scopeChipLabel('project')).toBe('Project');
  });
  it('returns "Global" for global', () => {
    expect(scopeChipLabel('global')).toBe('Global');
  });
  it('returns "Developer" for developer', () => {
    expect(scopeChipLabel('developer')).toBe('Developer');
  });
});

describe('scopeAriaLabel', () => {
  it('describes project-scope', () => {
    expect(scopeAriaLabel('project')).toBe('Project-scoped setting');
  });
  it('describes global-scope', () => {
    expect(scopeAriaLabel('global')).toBe('Global-scoped setting');
  });
  it('describes developer-scope', () => {
    expect(scopeAriaLabel('developer')).toBe('Developer-only setting');
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd packages/ui && npx vitest run src/components/settings/__tests__/scope.test.ts`
Expected: FAIL — `Cannot find module '../scope'`

(If vitest is not yet installed in `packages/ui`, install it first: `cd packages/ui && npm install --save-dev vitest`. The dashboard pipeline tests in `packages/ui/src/components/pipeline/__tests__/` expect vitest to be wired; follow their existing pattern.)

- [ ] **Step 3: Create scope.ts**

```ts
// packages/ui/src/components/settings/scope.ts
export type SettingsScope = 'project' | 'global' | 'developer';

export function scopeChipLabel(scope: SettingsScope): string {
  switch (scope) {
    case 'project': return 'Project';
    case 'global': return 'Global';
    case 'developer': return 'Developer';
  }
}

export function scopeAriaLabel(scope: SettingsScope): string {
  switch (scope) {
    case 'project': return 'Project-scoped setting';
    case 'global': return 'Global-scoped setting';
    case 'developer': return 'Developer-only setting';
  }
}
```

- [ ] **Step 4: Run test to confirm it passes**

Run: `cd packages/ui && npx vitest run src/components/settings/__tests__/scope.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/settings/scope.ts \
        packages/ui/src/components/settings/__tests__/scope.test.ts
git commit -m "feat(settings-v2): add scope helper types and labels"
```

---

## Task 2: `SettingRow` primitive

**Files:**
- Create: `packages/ui/src/components/settings/SettingRow.tsx`
- Create: `packages/ui/src/components/settings/__tests__/SettingRow.stories.tsx`

- [ ] **Step 1: Write the component**

```tsx
// packages/ui/src/components/settings/SettingRow.tsx
import { ReactNode } from 'react';
import { cn } from '../../lib/utils';  // existing @codrag/ui helper

export interface SettingRowProps {
  label: string;
  description?: ReactNode;
  control: ReactNode;
  /** suppresses the bottom border — use for the last row in a Section */
  last?: boolean;
  className?: string;
}

export function SettingRow({ label, description, control, last, className }: SettingRowProps) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-6 py-4',
        !last && 'border-b border-border-subtle',
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-text-primary">{label}</div>
        {description && (
          <div className="mt-1 text-sm text-text-muted">{description}</div>
        )}
      </div>
      <div className="flex-shrink-0 w-[260px] flex justify-end">
        {control}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write Storybook stories**

```tsx
// packages/ui/src/components/settings/__tests__/SettingRow.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { SettingRow } from '../SettingRow';

const meta: Meta<typeof SettingRow> = {
  title: 'Settings/SettingRow',
  component: SettingRow,
};
export default meta;

type Story = StoryObj<typeof SettingRow>;

export const WithToggle: Story = {
  args: {
    label: 'Enable tracing',
    description: 'Record import edges as files change.',
    control: <input type="checkbox" />,
  },
};

export const WithSelect: Story = {
  args: {
    label: 'Worktree location',
    description: 'Where to store git worktrees.',
    control: (
      <select className="border rounded-md px-2 py-1 text-sm">
        <option>Inside project (.claude/)</option>
        <option>External</option>
      </select>
    ),
  },
};

export const WithoutDescription: Story = {
  args: {
    label: 'Branch prefix',
    control: <input className="border rounded-md px-2 py-1 text-sm" defaultValue="claude" />,
  },
};

export const Last: Story = {
  args: {
    label: 'Final row',
    description: 'No bottom border.',
    control: <input type="checkbox" />,
    last: true,
  },
};
```

- [ ] **Step 3: Verify visually in Storybook**

Run: `cd packages/ui && npm run storybook`
Open: `http://localhost:6006` → Settings → SettingRow
Expected: All four stories render; toggles and selects align right at 260px; separator line visible except on `Last`.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/settings/SettingRow.tsx \
        packages/ui/src/components/settings/__tests__/SettingRow.stories.tsx
git commit -m "feat(settings-v2): add SettingRow primitive"
```

---

## Task 3: `Section` primitive

**Files:**
- Create: `packages/ui/src/components/settings/Section.tsx`
- Create: `packages/ui/src/components/settings/__tests__/Section.stories.tsx`

- [ ] **Step 1: Write the component**

```tsx
// packages/ui/src/components/settings/Section.tsx
import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface SectionProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Section({ title, children, className }: SectionProps) {
  return (
    <section className={cn(className)}>
      {title && (
        <h3 className="text-xs uppercase tracking-wide text-text-muted mb-2">
          {title}
        </h3>
      )}
      <div className="border border-border-subtle rounded-lg px-6 bg-surface-raised/30">
        {children}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Write Storybook story**

```tsx
// packages/ui/src/components/settings/__tests__/Section.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Section } from '../Section';
import { SettingRow } from '../SettingRow';

const meta: Meta<typeof Section> = { title: 'Settings/Section', component: Section };
export default meta;

export const Basic: StoryObj<typeof Section> = {
  render: () => (
    <Section title="General">
      <SettingRow label="One" control={<input type="checkbox" />} />
      <SettingRow label="Two" description="With description" control={<input type="checkbox" />} />
      <SettingRow label="Three" control={<input type="checkbox" />} last />
    </Section>
  ),
};

export const Untitled: StoryObj<typeof Section> = {
  render: () => (
    <Section>
      <SettingRow label="Solo row" control={<input type="checkbox" />} last />
    </Section>
  ),
};
```

- [ ] **Step 3: Verify visually in Storybook**

Run: `cd packages/ui && npm run storybook`
Expected: Section card has subtle border and tinted surface; title renders as uppercase muted label when present.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/settings/Section.tsx \
        packages/ui/src/components/settings/__tests__/Section.stories.tsx
git commit -m "feat(settings-v2): add Section primitive"
```

---

## Task 4: Barrel export settings primitives

**Files:**
- Modify: `packages/ui/src/index.ts`
- Create: `packages/ui/src/components/settings/index.ts`

- [ ] **Step 1: Create settings barrel**

```ts
// packages/ui/src/components/settings/index.ts
export { SettingRow } from './SettingRow';
export type { SettingRowProps } from './SettingRow';
export { Section } from './Section';
export type { SectionProps } from './Section';
export { scopeChipLabel, scopeAriaLabel } from './scope';
export type { SettingsScope } from './scope';
```

- [ ] **Step 2: Re-export from root barrel**

Add to `packages/ui/src/index.ts`:

```ts
export * from './components/settings';
```

- [ ] **Step 3: Build the UI package to verify typings**

Run: `cd packages/ui && npm run build`
Expected: no TypeScript errors; `dist/index.d.ts` includes `SettingRow`, `Section`, `SettingsScope`.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/settings/index.ts packages/ui/src/index.ts
git commit -m "feat(settings-v2): export settings primitives from @codrag/ui"
```

---

## Task 5: `routeParser` pure helper and test

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/routeParser.ts`
- Test: `src/codrag/dashboard/src/components/settings/v2/__tests__/routeParser.test.ts`

This extracts the URL-param logic so it can be unit tested without DOM.

- [ ] **Step 1: Write the failing test**

```ts
// src/codrag/dashboard/src/components/settings/v2/__tests__/routeParser.test.ts
import { describe, it, expect } from 'vitest';
import {
  PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES,
  parseSettingsParam, buildSettingsParam, isKnownPage,
} from '../routeParser';

describe('parseSettingsParam', () => {
  it('returns null when search string has no settings param', () => {
    expect(parseSettingsParam('?foo=bar')).toBeNull();
  });
  it('returns the page id when present and known', () => {
    expect(parseSettingsParam('?settings=sources')).toBe('sources');
  });
  it('returns null when the page id is unknown', () => {
    expect(parseSettingsParam('?settings=not-a-page')).toBeNull();
  });
  it('preserves hyphenated page ids', () => {
    expect(parseSettingsParam('?settings=trace-indexing')).toBe('trace-indexing');
  });
});

describe('buildSettingsParam', () => {
  it('writes the param preserving other query keys', () => {
    const s = buildSettingsParam('?foo=bar', 'appearance');
    expect(s).toContain('foo=bar');
    expect(s).toContain('settings=appearance');
  });
  it('removes the param when page is null', () => {
    const s = buildSettingsParam('?foo=bar&settings=sources', null);
    expect(s).toContain('foo=bar');
    expect(s).not.toContain('settings=');
  });
});

describe('isKnownPage', () => {
  it('accepts every Project page', () => {
    for (const p of PROJECT_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('accepts every Global page', () => {
    for (const p of GLOBAL_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('accepts every Developer page', () => {
    for (const p of DEVELOPER_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('rejects unknown ids', () => {
    expect(isKnownPage('zzz')).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/routeParser.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `routeParser.ts`**

```ts
// src/codrag/dashboard/src/components/settings/v2/routeParser.ts
export const PROJECT_PAGES = [
  'sources', 'trace-indexing', 'deep-analysis', 'danger-zone',
] as const;

export const GLOBAL_PAGES = [
  'appearance', 'chunking-embeddings', 'pipeline-defaults', 'license', 'integrations',
] as const;

export const DEVELOPER_PAGES = [
  'developer-debug', 'developer-diagnostics', 'developer-reset',
] as const;

export type ProjectPageId = typeof PROJECT_PAGES[number];
export type GlobalPageId = typeof GLOBAL_PAGES[number];
export type DeveloperPageId = typeof DEVELOPER_PAGES[number];
export type SettingsPageId = ProjectPageId | GlobalPageId | DeveloperPageId;

const ALL: readonly string[] = [...PROJECT_PAGES, ...GLOBAL_PAGES, ...DEVELOPER_PAGES];

export function isKnownPage(id: string): id is SettingsPageId {
  return ALL.includes(id);
}

export function parseSettingsParam(search: string): SettingsPageId | null {
  const params = new URLSearchParams(search);
  const raw = params.get('settings');
  if (!raw) return null;
  return isKnownPage(raw) ? raw : null;
}

export function buildSettingsParam(search: string, page: SettingsPageId | null): string {
  const params = new URLSearchParams(search);
  if (page === null) params.delete('settings');
  else params.set('settings', page);
  const out = params.toString();
  return out ? `?${out}` : '';
}

export function scopeForPage(id: SettingsPageId): 'project' | 'global' | 'developer' {
  if ((PROJECT_PAGES as readonly string[]).includes(id)) return 'project';
  if ((GLOBAL_PAGES as readonly string[]).includes(id)) return 'global';
  return 'developer';
}
```

- [ ] **Step 4: Run test to confirm it passes**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/routeParser.test.ts`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/routeParser.ts \
        src/codrag/dashboard/src/components/settings/v2/__tests__/routeParser.test.ts
git commit -m "feat(settings-v2): add pure URL-param route parser"
```

---

## Task 6: `devGate` helper and test

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/devGate.ts`
- Test: `src/codrag/dashboard/src/components/settings/v2/__tests__/devGate.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/codrag/dashboard/src/components/settings/v2/__tests__/devGate.test.ts
import { describe, it, expect } from 'vitest';
import { filterPagesForBuild } from '../devGate';
import { PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES } from '../routeParser';

describe('filterPagesForBuild', () => {
  it('keeps all pages in dev builds', () => {
    const result = filterPagesForBuild(true);
    expect(result.project).toEqual([...PROJECT_PAGES]);
    expect(result.global).toEqual([...GLOBAL_PAGES]);
    expect(result.developer).toEqual([...DEVELOPER_PAGES]);
  });
  it('drops Developer pages in production builds', () => {
    const result = filterPagesForBuild(false);
    expect(result.project).toEqual([...PROJECT_PAGES]);
    expect(result.global).toEqual([...GLOBAL_PAGES]);
    expect(result.developer).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/devGate.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `devGate.ts`**

```ts
// src/codrag/dashboard/src/components/settings/v2/devGate.ts
import { PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES } from './routeParser';
import type { SettingsPageId } from './routeParser';

export function isDevBuild(): boolean {
  return !!import.meta.env.DEV;
}

export interface PageSet {
  project: readonly SettingsPageId[];
  global: readonly SettingsPageId[];
  developer: readonly SettingsPageId[];
}

export function filterPagesForBuild(dev: boolean): PageSet {
  return {
    project: [...PROJECT_PAGES],
    global: [...GLOBAL_PAGES],
    developer: dev ? [...DEVELOPER_PAGES] : [],
  };
}
```

- [ ] **Step 4: Run test to confirm it passes**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/devGate.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/devGate.ts \
        src/codrag/dashboard/src/components/settings/v2/__tests__/devGate.test.ts
git commit -m "feat(settings-v2): add build-time Developer-page gate"
```

---

## Task 7: Dirty-flag helper and test

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/useSettingsDirty.ts`
- Test: `src/codrag/dashboard/src/components/settings/v2/__tests__/dirty.test.ts`

The hook itself wraps `useState`/`useEffect`. Extract the pure reducer so we can test it without render.

- [ ] **Step 1: Write the failing test**

```ts
// src/codrag/dashboard/src/components/settings/v2/__tests__/dirty.test.ts
import { describe, it, expect } from 'vitest';
import { dirtyReducer, DirtyState } from '../useSettingsDirty';

const initial: DirtyState = { dirty: false, saving: false };

describe('dirtyReducer', () => {
  it('marks dirty on EDIT', () => {
    expect(dirtyReducer(initial, { type: 'EDIT' })).toEqual({ dirty: true, saving: false });
  });
  it('marks saving on SAVE_START', () => {
    expect(dirtyReducer({ dirty: true, saving: false }, { type: 'SAVE_START' }))
      .toEqual({ dirty: true, saving: true });
  });
  it('clears dirty on SAVE_SUCCESS', () => {
    expect(dirtyReducer({ dirty: true, saving: true }, { type: 'SAVE_SUCCESS' }))
      .toEqual({ dirty: false, saving: false });
  });
  it('keeps dirty on SAVE_ERROR', () => {
    expect(dirtyReducer({ dirty: true, saving: true }, { type: 'SAVE_ERROR' }))
      .toEqual({ dirty: true, saving: false });
  });
  it('clears dirty on DISCARD', () => {
    expect(dirtyReducer({ dirty: true, saving: false }, { type: 'DISCARD' }))
      .toEqual({ dirty: false, saving: false });
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/dirty.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the hook and reducer**

```ts
// src/codrag/dashboard/src/components/settings/v2/useSettingsDirty.ts
import { useReducer, useCallback } from 'react';

export interface DirtyState {
  dirty: boolean;
  saving: boolean;
}

export type DirtyAction =
  | { type: 'EDIT' }
  | { type: 'SAVE_START' }
  | { type: 'SAVE_SUCCESS' }
  | { type: 'SAVE_ERROR' }
  | { type: 'DISCARD' };

export function dirtyReducer(state: DirtyState, action: DirtyAction): DirtyState {
  switch (action.type) {
    case 'EDIT':         return { ...state, dirty: true };
    case 'SAVE_START':   return { ...state, saving: true };
    case 'SAVE_SUCCESS': return { dirty: false, saving: false };
    case 'SAVE_ERROR':   return { ...state, saving: false };
    case 'DISCARD':      return { dirty: false, saving: false };
  }
}

export function useSettingsDirty() {
  const [state, dispatch] = useReducer(dirtyReducer, { dirty: false, saving: false });
  const markEdited = useCallback(() => dispatch({ type: 'EDIT' }), []);
  const startSave  = useCallback(() => dispatch({ type: 'SAVE_START' }), []);
  const finishSave = useCallback((ok: boolean) =>
    dispatch({ type: ok ? 'SAVE_SUCCESS' : 'SAVE_ERROR' }), []);
  const discard    = useCallback(() => dispatch({ type: 'DISCARD' }), []);
  return { ...state, markEdited, startSave, finishSave, discard };
}
```

- [ ] **Step 4: Run test to confirm it passes**

Run: `cd src/codrag/dashboard && npx vitest run src/components/settings/v2/__tests__/dirty.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/useSettingsDirty.ts \
        src/codrag/dashboard/src/components/settings/v2/__tests__/dirty.test.ts
git commit -m "feat(settings-v2): add useSettingsDirty hook with pure reducer"
```

---

## Task 8: `useSettingsRoute` hook

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/useSettingsRoute.ts`

No DOM test; logic is exercised by `routeParser` unit tests. Hook is a thin wrapper on top.

- [ ] **Step 1: Implement the hook**

```ts
// src/codrag/dashboard/src/components/settings/v2/useSettingsRoute.ts
import { useCallback, useEffect, useState } from 'react';
import {
  parseSettingsParam, buildSettingsParam, type SettingsPageId,
} from './routeParser';

/**
 * Reads `?settings=<page>` and exposes a setter that updates the URL via
 * replaceState (no history spam) while syncing an internal React state.
 */
export function useSettingsRoute() {
  const [page, setPageState] = useState<SettingsPageId | null>(
    () => parseSettingsParam(window.location.search),
  );

  useEffect(() => {
    const onPop = () => setPageState(parseSettingsParam(window.location.search));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const setPage = useCallback((next: SettingsPageId | null) => {
    const nextSearch = buildSettingsParam(window.location.search, next);
    const url = window.location.pathname + nextSearch + window.location.hash;
    // replaceState: clicking nav items does not pollute history
    window.history.replaceState(window.history.state, '', url);
    setPageState(next);
  }, []);

  const openAt = useCallback((next: SettingsPageId) => {
    const nextSearch = buildSettingsParam(window.location.search, next);
    const url = window.location.pathname + nextSearch + window.location.hash;
    // pushState: opening settings creates a single history entry so
    // browser back closes it.
    window.history.pushState(window.history.state, '', url);
    setPageState(next);
  }, []);

  const close = useCallback(() => {
    const nextSearch = buildSettingsParam(window.location.search, null);
    const url = window.location.pathname + nextSearch + window.location.hash;
    window.history.replaceState(window.history.state, '', url);
    setPageState(null);
  }, []);

  return { page, setPage, openAt, close };
}
```

- [ ] **Step 2: Typecheck**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/useSettingsRoute.ts
git commit -m "feat(settings-v2): add useSettingsRoute hook"
```

---

## Task 9: `SettingsPage` wrapper

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/SettingsPage.tsx`

- [ ] **Step 1: Implement**

```tsx
// src/codrag/dashboard/src/components/settings/v2/SettingsPage.tsx
import { ReactNode } from 'react';
import { scopeChipLabel, scopeAriaLabel, type SettingsScope } from '@codrag/ui';

export interface SettingsPageProps {
  title: string;
  scope: SettingsScope;
  description?: ReactNode;
  /** right-aligned header actions — Save button for Project pages */
  actions?: ReactNode;
  /** "Unsaved changes" banner (Project pages) */
  dirty?: boolean;
  children: ReactNode;
}

export function SettingsPage({
  title, scope, description, actions, dirty, children,
}: SettingsPageProps) {
  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <header
        className="sticky top-0 bg-surface-canvas z-10 pb-4 border-b border-border-subtle mb-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
              <span
                className="bg-surface-subtle text-text-muted text-xs rounded-full px-2 py-0.5"
                aria-label={scopeAriaLabel(scope)}
              >
                {scopeChipLabel(scope)}
              </span>
            </div>
            {description && (
              <p className="mt-1 text-sm text-text-muted">{description}</p>
            )}
          </div>
          {actions && <div className="flex-shrink-0">{actions}</div>}
        </div>
        {dirty && (
          <div className="mt-3 rounded-md bg-warning-subtle text-warning-strong text-sm px-3 py-2">
            Unsaved changes
          </div>
        )}
      </header>

      <div className="space-y-8">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: no errors. If `bg-warning-subtle` / `text-warning-strong` tokens aren't in the current Tailwind config, substitute the equivalent tokens that exist — check `packages/ui/tailwind.config.*` and `packages/ui/src/tokens/` for the warning-color family. Do **not** use raw colors.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/SettingsPage.tsx
git commit -m "feat(settings-v2): add SettingsPage wrapper with scope chip"
```

---

## Task 10: `SettingsNav`

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/SettingsNav.tsx`

- [ ] **Step 1: Implement**

```tsx
// src/codrag/dashboard/src/components/settings/v2/SettingsNav.tsx
import { cn } from '@codrag/ui';
import type { SettingsPageId } from './routeParser';
import { filterPagesForBuild, isDevBuild } from './devGate';

export interface SettingsNavProps {
  activePage: SettingsPageId | null;
  onNavigate: (page: SettingsPageId) => void;
  /** project name to show in the group label; null if no project active */
  projectName: string | null;
}

const LABELS: Record<SettingsPageId, string> = {
  'sources': 'Sources & Scope',
  'trace-indexing': 'Trace & Indexing',
  'deep-analysis': 'Deep Analysis',
  'danger-zone': 'Danger Zone',
  'appearance': 'Appearance',
  'chunking-embeddings': 'Chunking & Embeddings',
  'pipeline-defaults': 'Pipeline Defaults',
  'license': 'License',
  'integrations': 'Integrations',
  'developer-debug': 'Debug Toggles',
  'developer-diagnostics': 'Diagnostics',
  'developer-reset': 'Selective Reset',
};

export function SettingsNav({ activePage, onNavigate, projectName }: SettingsNavProps) {
  const pages = filterPagesForBuild(isDevBuild());
  const projectDisabled = projectName === null;

  const renderItem = (id: SettingsPageId, disabled = false) => (
    <button
      key={id}
      type="button"
      disabled={disabled}
      aria-current={activePage === id ? 'page' : undefined}
      onClick={() => !disabled && onNavigate(id)}
      className={cn(
        'w-full text-left text-sm rounded-md mx-0 px-3 py-1.5',
        disabled
          ? 'text-text-disabled cursor-not-allowed'
          : 'text-text-secondary hover:bg-surface-subtle cursor-pointer',
        activePage === id && !disabled && 'bg-surface-subtle text-text-primary font-medium',
      )}
    >
      {LABELS[id]}
    </button>
  );

  return (
    <nav aria-label="Settings" className="w-60 border-r border-border-subtle overflow-y-auto py-2">
      <div className="px-3">
        <div className="text-xs uppercase tracking-wide text-text-muted pt-4 pb-1">
          {projectDisabled
            ? 'Project · none selected'
            : `Project · ${projectName}`}
        </div>
        <div className="space-y-0.5">
          {pages.project.map(id => renderItem(id, projectDisabled))}
        </div>
        {projectDisabled && (
          <p className="text-xs text-text-muted mt-2 px-1">Select a project first.</p>
        )}
      </div>

      <div className="border-t border-border-subtle mt-4 pt-2 px-3">
        <div className="text-xs uppercase tracking-wide text-text-muted pt-2 pb-1">Global</div>
        <div className="space-y-0.5">
          {pages.global.map(id => renderItem(id))}
        </div>
      </div>

      {pages.developer.length > 0 && (
        <div className="border-t border-border-subtle mt-4 pt-2 px-3">
          <div className="text-xs uppercase tracking-wide text-text-muted pt-2 pb-1">
            Developer
          </div>
          <div className="space-y-0.5">
            {pages.developer.map(id => renderItem(id))}
          </div>
        </div>
      )}
    </nav>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/SettingsNav.tsx
git commit -m "feat(settings-v2): add SettingsNav with scope-split groups"
```

---

## Task 11: `SettingsOverlay` container

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/SettingsOverlay.tsx`

- [ ] **Step 1: Implement the shell**

```tsx
// src/codrag/dashboard/src/components/settings/v2/SettingsOverlay.tsx
import { createPortal } from 'react-dom';
import { useEffect, useRef } from 'react';
import { ArrowLeft, X } from 'lucide-react';
import { cn } from '@codrag/ui';
import { SettingsNav } from './SettingsNav';
import { useSettingsRoute } from './useSettingsRoute';
import type { SettingsPageId } from './routeParser';

export interface SettingsOverlayProps {
  /** page body renderer — host wires this to the page registry */
  renderPage: (page: SettingsPageId) => React.ReactNode;
  /** active project name for the nav group label; null disables Project nav */
  projectName: string | null;
  /** called when user tries to close but a Project page is dirty; returns true if safe to close */
  confirmCloseIfDirty?: () => boolean;
}

export function SettingsOverlay({
  renderPage, projectName, confirmCloseIfDirty,
}: SettingsOverlayProps) {
  const { page, setPage, close } = useSettingsRoute();
  const backRef = useRef<HTMLButtonElement>(null);

  // Focus back-arrow when the overlay opens
  useEffect(() => {
    if (page !== null) backRef.current?.focus();
  }, [page]);

  // Esc closes
  useEffect(() => {
    if (page === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [page, close, confirmCloseIfDirty]);

  if (page === null) return null;

  return createPortal(
    <div
      className={cn(
        'fixed inset-0 z-50 bg-surface-canvas',
        'flex flex-col',
        'animate-settings-overlay-in',
      )}
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <header className="h-14 border-b border-border-subtle px-4 flex items-center gap-3">
        <button
          ref={backRef}
          type="button"
          onClick={() => {
            if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
          }}
          aria-label="Close settings"
          className="p-1 rounded-md hover:bg-surface-subtle text-text-secondary"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h2 className="text-base font-medium text-text-primary">Settings</h2>
        <div className="ml-auto flex items-center gap-2">
          <kbd className="text-xs text-text-muted bg-surface-subtle rounded px-1.5 py-0.5">⌘,</kbd>
          <button
            type="button"
            onClick={() => {
              if (!confirmCloseIfDirty || confirmCloseIfDirty()) close();
            }}
            aria-label="Close settings"
            className="p-1 rounded-md hover:bg-surface-subtle text-text-secondary"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <SettingsNav
          activePage={page}
          onNavigate={setPage}
          projectName={projectName}
        />
        <main className="flex-1 overflow-y-auto">
          {renderPage(page)}
        </main>
      </div>
    </div>,
    document.body,
  );
}
```

- [ ] **Step 2: Add the overlay animation**

Add to the dashboard's global CSS (`src/codrag/dashboard/src/index.css` or wherever Tailwind `@layer utilities` already lives):

```css
@keyframes settings-overlay-in {
  from { opacity: 0; transform: scale(0.96); transform-origin: bottom right; }
  to   { opacity: 1; transform: scale(1);     transform-origin: bottom right; }
}
.animate-settings-overlay-in {
  animation: settings-overlay-in 180ms ease-out;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/SettingsOverlay.tsx \
        src/codrag/dashboard/src/index.css
git commit -m "feat(settings-v2): add SettingsOverlay portal container"
```

---

## Task 12: `⌘,` shortcut and flag wiring in `App.tsx`

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx`

**Reading tasks before editing:** open `App.tsx` and locate (a) where `SettingsDrawer` is currently mounted (search for `SettingsDrawer`), (b) where the floating Settings button handler lives, (c) where global keyboard shortcuts are registered (if at all). Keep existing drawer mount — the flag decides which renders.

- [ ] **Step 1: Add flag read**

Near the top of `App.tsx`, add:

```ts
const settingsV2Enabled = localStorage.getItem('codrag_settings_overlay_v2') === '1'
  || import.meta.env.DEV;  // dev builds default on
```

- [ ] **Step 2: Import the overlay and page registry**

```ts
import { SettingsOverlay } from './components/settings/v2/SettingsOverlay';
import { renderSettingsPage } from './components/settings/v2/pages';  // barrel, created in Task 13
```

- [ ] **Step 3: Mount the overlay next to the drawer, conditionally**

Find the JSX where `<SettingsDrawer … />` is rendered. Wrap both in a conditional:

```tsx
{settingsV2Enabled ? (
  <SettingsOverlay
    renderPage={(page) => renderSettingsPage(page, {
      projectConfig, globalConfig, activeProjectId, /* etc — existing props */
    })}
    projectName={activeProject?.name ?? null}
    confirmCloseIfDirty={() => {
      if (!projectDirty) return true;
      return window.confirm('Discard unsaved project changes?');
    }}
  />
) : (
  <SettingsDrawer … /* existing props */ />
)}
```

- [ ] **Step 4: Wire `⌘,` keyboard shortcut**

Add a `useEffect` at the top of the `App` component:

```tsx
useEffect(() => {
  if (!settingsV2Enabled) return;
  const onKey = (e: KeyboardEvent) => {
    const mod = navigator.platform.includes('Mac') ? e.metaKey : e.ctrlKey;
    if (mod && e.key === ',') {
      e.preventDefault();
      const current = new URLSearchParams(window.location.search).get('settings');
      if (current) {
        // close by navigating back; SettingsOverlay listens to popstate
        window.history.back();
      } else {
        const next = new URL(window.location.href);
        next.searchParams.set('settings', 'sources');
        window.history.pushState(window.history.state, '', next.toString());
        window.dispatchEvent(new PopStateEvent('popstate'));
      }
    }
  };
  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}, [settingsV2Enabled]);
```

- [ ] **Step 5: Typecheck + manual verify**

Run: `cd src/codrag/dashboard && npx tsc --noEmit` → expected no errors.
Run: `scripts/dev.sh` → open dashboard at `:5174`, press `⌘,` → overlay should appear with nav rail and an empty main area (pages don't exist yet).
Press `Esc` → overlay should close.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/App.tsx
git commit -m "feat(settings-v2): mount SettingsOverlay behind flag with ⌘, shortcut"
```

---

## Task 13: Page registry barrel + stub pages

**Files:**
- Create: `src/codrag/dashboard/src/components/settings/v2/pages/index.tsx`
- Create: 12 stub pages (`Sources.tsx`, `TraceIndexing.tsx`, `DeepAnalysis.tsx`, `DangerZone.tsx`, `Appearance.tsx`, `ChunkingEmbeddings.tsx`, `PipelineDefaults.tsx`, `License.tsx`, `Integrations.tsx`, `DevToggles.tsx`, `Diagnostics.tsx`, `SelectiveReset.tsx`)

Stubs render only the `SettingsPage` wrapper with the right title + scope. Subsequent tasks (14–22) fill them in.

- [ ] **Step 1: Create one stub for each page**

Example for Sources. Repeat the pattern for the other 11 files, changing `title`, `scope`, `description`.

```tsx
// src/codrag/dashboard/src/components/settings/v2/pages/Sources.tsx
import { SettingsPage } from '../SettingsPage';

export interface SourcesPageProps {
  // filled in Task 14
}

export function SourcesPage(_props: SourcesPageProps) {
  return (
    <SettingsPage
      title="Sources & Scope"
      scope="project"
      description="Which files are included in this project's index."
    >
      <div className="text-sm text-text-muted">Coming soon.</div>
    </SettingsPage>
  );
}
```

**Titles and scopes for each stub:**

| File | Title | Scope | Description |
|------|-------|-------|-------------|
| Sources.tsx | Sources & Scope | project | Which files are included in this project's index. |
| TraceIndexing.tsx | Trace & Indexing | project | How the trace graph is built and refreshed. |
| DeepAnalysis.tsx | Deep Analysis | project | LLM-assisted enrichment and its budgets. |
| DangerZone.tsx | Danger Zone | project | Destructive operations. Each requires typed confirmation. |
| Appearance.tsx | Appearance | global | Theme, colour mode, and background. |
| ChunkingEmbeddings.tsx | Chunking & Embeddings | global | How source files are split for embedding. |
| PipelineDefaults.tsx | Pipeline Defaults | global | Daemon-wide pipeline parameters. |
| License.tsx | License | global | Subscription tier and activation. |
| Integrations.tsx | Integrations | global | Connected IDEs and the AI Gateway. |
| DevToggles.tsx | Debug Toggles | developer | Runtime flags for developers. |
| Diagnostics.tsx | Diagnostics | developer | Daemon health, data directory, licence details. |
| SelectiveReset.tsx | Selective Reset | developer | Reset individual caches without a full rebuild. |

- [ ] **Step 2: Page registry barrel**

```tsx
// src/codrag/dashboard/src/components/settings/v2/pages/index.tsx
import type { SettingsPageId } from '../routeParser';
import { SourcesPage } from './Sources';
import { TraceIndexingPage } from './TraceIndexing';
import { DeepAnalysisPage } from './DeepAnalysis';
import { DangerZonePage } from './DangerZone';
import { AppearancePage } from './Appearance';
import { ChunkingEmbeddingsPage } from './ChunkingEmbeddings';
import { PipelineDefaultsPage } from './PipelineDefaults';
import { LicensePage } from './License';
import { IntegrationsPage } from './Integrations';
import { DevTogglesPage } from './DevToggles';
import { DiagnosticsPage } from './Diagnostics';
import { SelectiveResetPage } from './SelectiveReset';

export interface PageHostProps {
  // shared props the host App passes through; tasks 14–22 extend as needed
  projectConfig: unknown;
  globalConfig: unknown;
  activeProjectId: string | null;
  // …any other props the lifted JSX reads
}

export function renderSettingsPage(id: SettingsPageId, host: PageHostProps) {
  switch (id) {
    case 'sources':             return <SourcesPage {...host as any} />;
    case 'trace-indexing':      return <TraceIndexingPage {...host as any} />;
    case 'deep-analysis':       return <DeepAnalysisPage {...host as any} />;
    case 'danger-zone':         return <DangerZonePage {...host as any} />;
    case 'appearance':          return <AppearancePage {...host as any} />;
    case 'chunking-embeddings': return <ChunkingEmbeddingsPage {...host as any} />;
    case 'pipeline-defaults':   return <PipelineDefaultsPage {...host as any} />;
    case 'license':             return <LicensePage {...host as any} />;
    case 'integrations':        return <IntegrationsPage {...host as any} />;
    case 'developer-debug':     return <DevTogglesPage {...host as any} />;
    case 'developer-diagnostics': return <DiagnosticsPage {...host as any} />;
    case 'developer-reset':     return <SelectiveResetPage {...host as any} />;
  }
}
```

**NOTE on `as any`:** this is a temporary affordance so the barrel typechecks before the per-page props (tasks 14–22) are finalized. Each page task replaces `as any` with its concrete interface.

- [ ] **Step 3: Typecheck + manual verify**

Run: `cd src/codrag/dashboard && npx tsc --noEmit` → expected no errors.
Run: `scripts/dev.sh` → press `⌘,`, click each nav item, confirm each stub page renders with correct title and scope chip.

- [ ] **Step 4: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/pages/
git commit -m "feat(settings-v2): scaffold 12 stub pages behind the overlay"
```

---

## Task 14: Lift — Sources & Scope page (Project)

**Source:** lines 286–392 of `SettingsDrawer.tsx` (the `activeTab === 'project' && hasProject` block).

**Files:**
- Modify: `src/codrag/dashboard/src/components/settings/v2/pages/Sources.tsx`

Follow the **Lift Template** from the top of this plan.

- [ ] **Step 1: Read the source**

Open `SettingsDrawer.tsx` and identify all controls in the Project tab that relate to sources: include/exclude globs, preset detection, gitignore toggle, max file bytes, hard-limit bytes, active flag, priority level.

Deep Analysis controls (mode, budget, schedule) stay behind for Task 16. Danger Zone stays behind for Task 17.

- [ ] **Step 2: Define the page props**

```tsx
// src/codrag/dashboard/src/components/settings/v2/pages/Sources.tsx
import { SettingsPage } from '../SettingsPage';
import { SettingRow, Section } from '@codrag/ui';
import type { ProjectConfig } from '../../../../types';

export interface SourcesPageProps {
  projectName: string;
  config: ProjectConfig;
  dirty: boolean;
  onChange: (patch: Partial<ProjectConfig>) => void;
  onSave: () => void | Promise<void>;
  onDiscard: () => void;
  saving: boolean;
}

export function SourcesPage({
  projectName, config, dirty, onChange, onSave, onDiscard, saving,
}: SourcesPageProps) {
  return (
    <SettingsPage
      title="Sources & Scope"
      scope="project"
      description={`Which files are included in ${projectName}'s index.`}
      dirty={dirty}
      actions={
        <div className="flex gap-2">
          {dirty && (
            <button
              type="button"
              onClick={onDiscard}
              disabled={saving}
              className="text-sm text-text-secondary hover:text-text-primary px-3 py-1.5 rounded-md"
            >Discard</button>
          )}
          <button
            type="button"
            onClick={onSave}
            disabled={!dirty || saving}
            className="text-sm bg-accent-primary text-on-accent px-3 py-1.5 rounded-md disabled:opacity-50"
          >{saving ? 'Saving…' : 'Save'}</button>
        </div>
      }
    >
      <Section>
        {/* lifted controls, each wrapped in <SettingRow> */}
        {/* Include globs: textarea — see drawer source for exact copy */}
        <SettingRow
          label="Include globs"
          description="Patterns to include (one per line)."
          control={<textarea
            value={config.include_globs?.join('\n') ?? ''}
            onChange={(e) => onChange({ include_globs: e.target.value.split('\n').filter(Boolean) })}
            className="w-[260px] h-24 border rounded-md px-2 py-1 text-sm"
          />}
        />
        {/* Exclude globs, max_file_bytes, hard_limit_bytes, use_gitignore,
            active, priority_level — one SettingRow each, copying labels
            and help text verbatim from SettingsDrawer.tsx */}
        {/* Mark the final row with last={true} to drop the bottom border */}
      </Section>
    </SettingsPage>
  );
}
```

- [ ] **Step 3: Remove `as any` in the registry barrel**

Update `pages/index.tsx`:

```tsx
case 'sources':
  return <SourcesPage
    projectName={host.projectName}
    config={host.projectConfig}
    dirty={host.projectDirty}
    onChange={host.onProjectChange}
    onSave={host.onProjectSave}
    onDiscard={host.onProjectDiscard}
    saving={host.projectSaving}
  />;
```

…and extend `PageHostProps` with the corresponding fields. The host (`App.tsx`) already owns this state — pass it through.

- [ ] **Step 4: Manual verify**

Run: `scripts/dev.sh` → press `⌘,` → select Sources & Scope.
Confirm every control from the old Project tab is present with the same label and help text. Edit a glob; `Unsaved changes` banner appears; click Save; banner clears and `GET /projects/{id}/settings` on reload returns the new value.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/v2/pages/Sources.tsx \
        src/codrag/dashboard/src/components/settings/v2/pages/index.tsx \
        src/codrag/dashboard/src/App.tsx
git commit -m "feat(settings-v2): lift Sources & Scope page from drawer"
```

---

## Task 15: Lift — Trace & Indexing page (Project)

**Sources:**
- `SettingsDrawer.tsx` Project tab: per-project trace controls (trace enable, ignore patterns, auto-rebuild debounce, graph_engine advanced).
- `AdvancedSettingsPanel.tsx` per-project block: `max_files`, `max_nodes`, `max_edges` trace limits.

Follow the Lift Template. Two `<Section>` blocks: "Trace" and "Trace Limits". Project scope. Preserves dirty/save flow.

- [ ] **Step 1: Identify controls in both source files**

Grep `SettingsDrawer.tsx` for `trace.enabled`, `trace.ignore_patterns`, `auto_rebuild`, `graph_engine` — lift these.
Grep `AdvancedSettingsPanel.tsx` for `max_files`, `max_nodes`, `max_edges` — lift into a "Trace Limits" section.

- [ ] **Step 2: Implement `TraceIndexing.tsx`**

Same shape as Sources.tsx: `SettingsPage` wrapper (scope=project, dirty/save wiring identical to Sources), then one `<Section>` for trace basics and a second `<Section title="Trace Limits">` for the numerics.

Copy labels and help text verbatim. Every form control wrapped in `<SettingRow>`.

- [ ] **Step 3: Update page registry**

Replace `as any` for `trace-indexing` case with concrete props (mirror Sources).

- [ ] **Step 4: Manual verify**

Open `?settings=trace-indexing`. Confirm all trace controls and all three trace-limit inputs render with the same labels as today. Edit + Save round-trips.

- [ ] **Step 5: Commit**

```bash
git add -- src/codrag/dashboard/src/components/settings/v2/pages/TraceIndexing.tsx \
           src/codrag/dashboard/src/components/settings/v2/pages/index.tsx
git commit -m "feat(settings-v2): lift Trace & Indexing page, absorb per-project trace limits"
```

---

## Task 16: Lift — Deep Analysis page (Project)

**Source:** `SettingsDrawer.tsx` Project tab — deep-enrichment schedule block (mode, budget tokens/minutes/items, auto_config flags for fastSync/deepEnrichment/finalize).

Follow the Lift Template. Project scope. One or two Sections.

- [ ] **Step 1: Lift into `DeepAnalysis.tsx`** with the same dirty/save pattern as Sources.
- [ ] **Step 2: Update registry.**
- [ ] **Step 3: Manual verify:** all deep-enrichment controls render identically; save round-trips.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift Deep Analysis page`

---

## Task 17: Lift — Danger Zone page (Project)

**Sources:**
- `SettingsDrawer.tsx` Project tab "Danger Zone" controls: Rebuild Pipeline, Reset Enrichment, Reset Finalize.
- `AdvancedSettingsPanel.tsx` "Reset All" button.

Project scope. No dirty/save (actions are one-shot). Preserve the Phase 114 typed-confirm UX for every destructive action.

- [ ] **Step 1: Lift all four buttons** into `DangerZone.tsx`. Each is a `SettingRow` whose `control` is the destructive button wrapped in its existing typed-confirm dialog component (reuse whatever `RebuildGate`-style component the drawer already uses — do not rewrite the confirmation logic).
- [ ] **Step 2: Update registry.**
- [ ] **Step 3: Manual verify:** each button opens its typed-confirm; typing the project name executes the action; wrong text disables the action button.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift Danger Zone page with Reset All absorbed`

---

## Task 18: Lift — Appearance page (Global)

**Source:** `SettingsDrawer.tsx` Global tab — color mode, theme selector, background image upload (lines ~398–460 area; verify).

Global scope → autosave on change (no Save button, no dirty banner).

- [ ] **Step 1: Lift into `Appearance.tsx`**. Each control calls the existing debounced `api.updateGlobalConfig` path; no dirty flag.
- [ ] **Step 2: Update registry:** `AppearancePage` takes `globalConfig` and `onGlobalChange` (the existing debounced setter).
- [ ] **Step 3: Manual verify:** flip theme; background persists on reload; colour mode persists on reload.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift Appearance page (global autosave)`

---

## Task 19: Lift — Chunking & Embeddings page (Global)

**Source:** `AdvancedSettingsPanel.tsx` global chunking block — code chunk size, overlap, markdown chunk sizes.

Global scope → autosave.

- [ ] **Step 1: Lift into `ChunkingEmbeddings.tsx`.**
- [ ] **Step 2: Update registry.**
- [ ] **Step 3: Manual verify:** edit chunk size, refresh, value persists.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift Chunking & Embeddings page from Advanced panel`

---

## Task 20: Lift — Pipeline Defaults page (Global)

**Sources:**
- `AdvancedSettingsPanel.tsx` global pipeline block — checkpoint interval, min_edge_confidence.
- `SettingsDrawer.tsx` Global tab — `max_active_projects`.

Global scope → autosave.

- [ ] **Step 1: Lift into `PipelineDefaults.tsx`** as two Sections if it reads better: "Concurrency" and "Thresholds".
- [ ] **Step 2: Update registry.**
- [ ] **Step 3: Manual verify:** values round-trip; `max_active_projects` does not appear in any other settings page.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift Pipeline Defaults page`

---

## Task 21: Lift — License page (Global)

**Source:** `SettingsDrawer.tsx` Global tab — license tier display, activation input. Move dev tier override and license details to the Developer Diagnostics page (Task 23).

Global scope → autosave (activation is explicit button, but the tier display has no edit).

- [ ] **Step 1: Lift into `License.tsx`.**
- [ ] **Step 2: Update registry.**
- [ ] **Step 3: Manual verify:** tier displayed; activation input accepts a licence key and calls the existing activation endpoint.
- [ ] **Step 4: Commit:** `feat(settings-v2): lift License page`

---

## Task 22: Build — Integrations page (Global)

**Source:** `SettingsDrawer.tsx` Global tab "AI Gateway shortcut" — the button that dispatches a custom event to open the AI Gateway panel.

Global scope. Single section. AI Gateway panel is **not moved** — only linked out.

- [ ] **Step 1: Implement `Integrations.tsx`**

```tsx
// src/codrag/dashboard/src/components/settings/v2/pages/Integrations.tsx
import { SettingsPage } from '../SettingsPage';
import { SettingRow, Section } from '@codrag/ui';

export interface IntegrationsPageProps {
  onOpenAiGateway: () => void;
}

export function IntegrationsPage({ onOpenAiGateway }: IntegrationsPageProps) {
  return (
    <SettingsPage
      title="Integrations"
      scope="global"
      description="Connected IDEs and the AI Gateway."
    >
      <Section>
        <SettingRow
          label="AI Gateway"
          description="Model slots, endpoints, and concurrency live in the AI Gateway panel."
          control={
            <button
              type="button"
              onClick={onOpenAiGateway}
              className="text-sm border border-border-subtle hover:bg-surface-subtle rounded-md px-3 py-1.5 text-text-primary"
            >Open AI Gateway →</button>
          }
          last
        />
      </Section>
    </SettingsPage>
  );
}
```

- [ ] **Step 2: Wire `onOpenAiGateway` in the App host**

Reuse the existing custom event the drawer dispatches (search for `dispatchEvent` in `SettingsDrawer.tsx` to find the event name). Opening the gateway should close the Settings overlay first, then dispatch the event. In the host:

```ts
const openAiGateway = () => {
  const next = new URL(window.location.href);
  next.searchParams.delete('settings');
  window.history.replaceState(window.history.state, '', next.toString());
  window.dispatchEvent(new CustomEvent('<existing-event-name>'));
};
```

- [ ] **Step 3: Update registry.**
- [ ] **Step 4: Manual verify:** click Open AI Gateway → overlay closes, AI Gateway panel opens. AI Gateway code is untouched.
- [ ] **Step 5: Commit:** `feat(settings-v2): add Integrations page with AI Gateway link-out`

---

## Task 23: Lift — Developer pages (dev-gated)

**Sources:** `SettingsDrawer.tsx` Developer tab (verbose telemetry, exploratory testing, show dev panels, role/tier override, license details, connection debugger) + `AdvancedSettingsPanel.tsx` Selective Reset (atlas, group_reasoning, deep_enrichment).

Split into three pages to match the nav:

- **`DevToggles.tsx`** — verbose telemetry, exploratory testing, show dev panels toggle (note: this is the dashboard-panel toggle, not the overlay gate; it stays), role/tier overrides.
- **`Diagnostics.tsx`** — connection debugger, daemon health, data dir status, dev tier badge, license details.
- **`SelectiveReset.tsx`** — reset atlas, reset group_reasoning, reset deep_enrichment.

All three are Developer scope → autosave for toggles, one-shot for buttons.

- [ ] **Step 1: Implement all three pages** using the Lift Template. For toggles, autosave through the existing global-config path.

- [ ] **Step 2: Update registry** — these three cases reference concrete props from the host.

- [ ] **Step 3: Verify dev-gate**
  - Dev build (`npm run dev`): all three pages are nav-accessible.
  - Production build: run `cd src/codrag/dashboard && npm run build && npm run preview` and open `http://localhost:4173/?settings=developer-debug` → overlay opens, Developer group is not in the nav, URL silently resets to `?settings=sources` (or the first Global page if no project is active).

- [ ] **Step 4: Add a safety belt in the overlay**

Open `SettingsOverlay.tsx`. In a `useEffect`, if the current page is a Developer page and `!isDevBuild()`, call `setPage('appearance')` (first Global page). This is the "defence in depth" redirect the spec mentions.

- [ ] **Step 5: Commit:** `feat(settings-v2): lift Developer pages (debug, diagnostics, selective reset) with build-time gate`

---

## Task 24: Flag flip and drawer removal

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx`
- Delete: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`
- Delete: `src/codrag/dashboard/src/components/settings/AdvancedSettingsPanel.tsx`

Dogfooding period has passed; v2 is the default. The flag stays for one more release as an opt-out escape hatch, then goes away.

- [ ] **Step 1: Default the flag to on**

In `App.tsx`, change:

```ts
const settingsV2Enabled = localStorage.getItem('codrag_settings_overlay_v2') === '1'
  || import.meta.env.DEV;
```

to:

```ts
const settingsV2Enabled = localStorage.getItem('codrag_settings_overlay_v2') !== '0';
```

Users who explicitly set `'0'` can still get the old drawer.

- [ ] **Step 2: Manual dogfood pass**

Run `scripts/dev.sh` and walk every page. Confirm every control in the new overlay matches its old-drawer counterpart by label and behaviour. Save/load every project page. Trigger every Danger Zone action on a scratch project.

- [ ] **Step 3: Remove the old drawer**

When you're satisfied:

- Delete `SettingsDrawer.tsx` and `AdvancedSettingsPanel.tsx`.
- Remove the drawer import, the drawer mount JSX, and the `settingsV2Enabled ? … : <SettingsDrawer />` conditional in `App.tsx` — render the overlay unconditionally.
- Remove the flag read and its localStorage key from `App.tsx`.
- Remove any `openToTab` / `setSettingsOpenToTab` state in the host that only existed to feed the drawer (check via grep).

- [ ] **Step 4: Typecheck + build**

Run: `cd src/codrag/dashboard && npx tsc --noEmit && npm run build`
Expected: both succeed.

- [ ] **Step 5: Commit**

```bash
git add -A src/codrag/dashboard/src/
git commit -m "refactor(settings-v2): make overlay default, delete drawer + advanced panel"
```

---

## Post-implementation: manual test checklist

Run `scripts/dev.sh` and verify each item:

- [ ] Floating Settings button bottom-right opens the overlay at the first Project page (or first Global page if no project active).
- [ ] `⌘,` / `Ctrl+,` opens and closes the overlay.
- [ ] `Esc` closes the overlay.
- [ ] Back-arrow top-left closes the overlay.
- [ ] URL param `?settings=<page>` deep-links to the page; browser reload preserves the page; share the URL from another window to confirm.
- [ ] Browser back button closes the overlay and leaves the dashboard exactly as it was before opening.
- [ ] Every Project nav item shows `Project · <name>` in the rail group label.
- [ ] With no project active, Project group is disabled with "Select a project first" hint.
- [ ] Each page shows the correct scope chip: Project / Global / Developer.
- [ ] Project pages show Save + Unsaved changes banner when dirty; Discard reverts; closing while dirty prompts confirmation.
- [ ] Global pages autosave; no Save button; no dirty banner.
- [ ] Every destructive action in Danger Zone still requires typed-confirm (Phase 114 pattern).
- [ ] Production build (`npm run build && npm run preview`) does not show the Developer group; `?settings=developer-debug` redirects to a Global page.
- [ ] `@codrag/ui` Storybook renders `SettingRow` and `Section` stories.
- [ ] AI Gateway panel, Pipeline Queue, left sidebar, and every dashboard panel are visually unchanged.
- [ ] `npx tsc --noEmit` passes for both `packages/ui` and `src/codrag/dashboard`.
- [ ] `cd packages/ui && npx vitest run` passes all existing + new tests.
- [ ] `cd src/codrag/dashboard && npx vitest run` passes all new tests.

---

## Self-Review Notes

**Spec coverage:**
- ✓ Three-group nav structure — Task 10.
- ✓ Full-screen overlay shell + transition — Task 11.
- ✓ Scope chip per page — Task 9.
- ✓ `SettingRow` / `Section` primitives with tokens — Tasks 2, 3.
- ✓ Scope-split save semantics — wired through Tasks 14–23 per-page.
- ✓ Dirty-flag guard — Tasks 7, 12 (overlay-level confirm).
- ✓ Keyboard `⌘,` — Task 12.
- ✓ URL param + deep-link + replaceState — Tasks 5, 8.
- ✓ Build-time gate + runtime redirect — Tasks 6, 23.
- ✓ Component inventory — every item in the spec's table has a task.
- ✓ Migration flag + rollout — Tasks 12, 24.
- ✓ Test strategy — pure-logic vitest + Storybook matches existing `HealthBadge` pattern.
- ✓ A11y — `role="dialog"`, `aria-modal`, `aria-current="page"`, `aria-label`s on scope chip and close button — Tasks 9, 10, 11.

**Type consistency sweep:**
- `SettingsPageId`, `ProjectPageId`, etc. — defined once in `routeParser.ts`, imported everywhere.
- `SettingsScope` — defined in `@codrag/ui/components/settings/scope.ts`, imported by `SettingsPage` and every page.
- `DirtyState`, `DirtyAction` — only used inside `useSettingsDirty.ts`; the hook exports state fields, not the raw types.
- Page component names: `SourcesPage`, `TraceIndexingPage`, `DeepAnalysisPage`, `DangerZonePage`, `AppearancePage`, `ChunkingEmbeddingsPage`, `PipelineDefaultsPage`, `LicensePage`, `IntegrationsPage`, `DevTogglesPage`, `DiagnosticsPage`, `SelectiveResetPage` — stable across the stub in Task 13 and each lift in Tasks 14–23.

**No placeholders** — every step that changes code shows the code or points to a verbatim lift from a specified source file with the labels/help text preserved.
