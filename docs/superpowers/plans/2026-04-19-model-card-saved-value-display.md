# ModelCard Saved-Value Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the AI Models panel regression where the Model dropdown shows "Select a model..." even though a model is persisted in config — by making `ModelCard`'s Model `<Select>` include the saved `model` value as an option when the fetched `availableModels` list doesn't contain it.

**Architecture:** Extract the option-building logic out of the JSX into a pure module-scope helper `buildModelOptions` inside `ModelCard.tsx` so it can be unit-tested the same way other `__tests__/` files in this package are (pure vitest, no DOM). The helper injects a synthetic option for the saved `model` when `availableModels` doesn't already contain it (with `:latest`-normalized matching), and suppresses the empty-value placeholder when a model is already saved so the native `<select>` cannot silently fall back to it.

**Tech Stack:** TypeScript, React, vitest (typecheck-only per existing convention), `@codrag/ui` package at `packages/ui/`.

---

## File Structure

- **Modify:** `packages/ui/src/components/llm/ModelCard.tsx` — extract `buildModelOptions` helper at module scope (exported); use it inside the Model `<Select>` options prop.
- **Create:** `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` — pure-logic vitest tests for `buildModelOptions`, following the `BarrierIndicator.test.tsx` / `HealthBadge.test.tsx` pattern (no DOM, no `@testing-library/react`).

No backend, API, persistence, types, or other UI files change. No new dependencies.

---

### Task 1: Add failing test for `buildModelOptions`

**Files:**
- Create: `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx`

Tests import `buildModelOptions` from `../ModelCard`. That export does not yet exist — this step is purely writing the test. Compilation will fail until Task 2 adds the export. That is the intended red state.

- [ ] **Step 1: Write the failing test file**

Create `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` with this exact content:

```tsx
/**
 * ModelCard tests
 *
 * Pure logic/unit tests following the BarrierIndicator.test.tsx pattern —
 * no DOM rendering, no @testing-library/react. These typecheck and run
 * with vitest once it is wired into the monorepo.
 *
 * Covers buildModelOptions — the helper that constructs the <Select>
 * option list for the Model dropdown. The key regression being fixed:
 * when a model is persisted in config but the endpoint's availableModels
 * list is empty (fetch not yet done, fetch failed, endpoint offline),
 * the native <select> must still render the saved value — not silently
 * fall back to the "Select a model..." placeholder.
 */
import { describe, it, expect } from 'vitest';
import { buildModelOptions } from '../ModelCard';

describe('buildModelOptions', () => {
  it('injects synthetic option for saved model when availableModels is empty', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: [],
      modelDetails: undefined,
      loadingModels: false,
    });
    // No placeholder (model is saved), just the synthetic entry.
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: 'qwen3:8b', label: 'qwen3:8b' });
  });

  it('does not duplicate when saved model is already in availableModels', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b', 'gemma3:12b'],
      modelDetails: undefined,
      loadingModels: false,
    });
    // No placeholder, no synthetic — just the two real entries.
    expect(opts).toHaveLength(2);
    expect(opts.map((o) => o.value)).toEqual(['qwen3:8b', 'gemma3:12b']);
  });

  it('treats ":latest" as equivalent when de-duping synthetic', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b:latest'],
      modelDetails: undefined,
      loadingModels: false,
    });
    // The saved model matches the :latest variant — no synthetic needed.
    expect(opts).toHaveLength(1);
    expect(opts[0].value).toBe('qwen3:8b:latest');
  });

  it('shows placeholder when no model is saved', () => {
    const opts = buildModelOptions({
      model: undefined,
      availableModels: [],
      modelDetails: undefined,
      loadingModels: false,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: '', label: 'Select a model...' });
  });

  it('shows loading placeholder when no model is saved and models are loading', () => {
    const opts = buildModelOptions({
      model: undefined,
      availableModels: [],
      modelDetails: undefined,
      loadingModels: true,
    });
    expect(opts).toHaveLength(1);
    expect(opts[0]).toEqual({ value: '', label: 'Loading models...' });
  });

  it('propagates blocked_by_policy flag onto matching options', () => {
    const opts = buildModelOptions({
      model: 'qwen3:8b',
      availableModels: ['qwen3:8b', 'gpt-5:cloud'],
      modelDetails: [
        { name: 'gpt-5:cloud', blocked_by_policy: true } as any,
      ],
      loadingModels: false,
    });
    expect(opts).toHaveLength(2);
    const blocked = opts.find((o) => o.value === 'gpt-5:cloud');
    expect(blocked?.disabled).toBe(true);
    expect(blocked?.label).toContain('Blocked by IT');
    const unblocked = opts.find((o) => o.value === 'qwen3:8b');
    expect(unblocked?.disabled).toBeFalsy();
  });
});
```

- [ ] **Step 2: Run typecheck to verify the test fails to compile (expected red state)**

Run from repo root:
```bash
cd packages/ui && npx tsc --noEmit
```

Expected output: one error like `src/components/llm/__tests__/ModelCard.test.tsx(...): error TS2305: Module '"../ModelCard"' has no exported member 'buildModelOptions'.` This confirms the test exists and targets an unimplemented export.

- [ ] **Step 3: Do not commit yet**

Leave the failing test uncommitted. Task 2 will add the implementation and then commit test + implementation together in a single green commit. (This repo's convention from recent commits uses tight feat/fix commits that ship passing work; keeping the red state staged-only avoids polluting history with a broken intermediate commit.)

---

### Task 2: Implement `buildModelOptions` and wire it into `ModelCard`

**Files:**
- Modify: `packages/ui/src/components/llm/ModelCard.tsx` (add module-scope helper around line 58; replace inline options array around lines 202–213)

- [ ] **Step 1: Add the `buildModelOptions` helper at module scope**

Open `packages/ui/src/components/llm/ModelCard.tsx`. Directly above the existing `export function ModelCard({ ... })` declaration (currently starting at line 59), insert the following block:

```tsx
/** Normalize a model name by stripping a trailing `:latest`. */
function stripLatest(name: string): string {
  return name.replace(/:latest$/, '');
}

/** True if `candidate` represents the same model as `saved` (handling `:latest`). */
function isSameModel(candidate: string, saved: string): boolean {
  if (candidate === saved) return true;
  if (candidate === `${saved}:latest`) return true;
  if (saved === `${candidate}:latest`) return true;
  return stripLatest(candidate) === stripLatest(saved);
}

export interface ModelOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface BuildModelOptionsArgs {
  model: string | undefined;
  availableModels: string[];
  modelDetails:
    | Array<{ name: string; [key: string]: unknown }>
    | undefined;
  loadingModels: boolean;
}

/**
 * Build the option list for the Model <Select>.
 *
 * Fixes a regression where a persisted `model` silently disappeared from
 * the dropdown whenever `availableModels` was empty (endpoint not yet
 * probed / probe failed / endpoint offline). The native <select> would
 * fall back to the empty-value placeholder, making it look as if nothing
 * was configured even though the backend still held the selection.
 *
 * Rules:
 *   1. If `model` is saved but NOT present in `availableModels`, prepend
 *      a synthetic `{ value: model, label: model }` so the native select
 *      can render the saved value.
 *   2. Only include the empty-value placeholder when `model` is unset.
 *      Otherwise the native select may prefer it over the saved value
 *      when no matching option exists.
 *   3. Carry the existing `blocked_by_policy` semantics onto entries
 *      derived from `availableModels`.
 */
export function buildModelOptions({
  model,
  availableModels,
  modelDetails,
  loadingModels,
}: BuildModelOptionsArgs): ModelOption[] {
  const hasSaved = !!model;
  const savedAlreadyListed =
    hasSaved && availableModels.some((m) => isSameModel(m, model!));

  const placeholder: ModelOption[] = hasSaved
    ? []
    : [{ value: '', label: loadingModels ? 'Loading models...' : 'Select a model...' }];

  const synthetic: ModelOption[] =
    hasSaved && !savedAlreadyListed ? [{ value: model!, label: model! }] : [];

  const fromAvailable: ModelOption[] = availableModels.map((m) => {
    const details = modelDetails?.find((d) => d.name === m);
    const isBlocked = (details as { blocked_by_policy?: boolean } | undefined)?.blocked_by_policy;
    return {
      value: m,
      label: isBlocked ? `🚫 ${m} (Blocked by IT)` : m,
      disabled: !!isBlocked,
    };
  });

  return [...placeholder, ...synthetic, ...fromAvailable];
}
```

- [ ] **Step 2: Replace the inline options array inside the component**

In the same file, find the Model selector block (currently lines ~198–215) that looks like:

```tsx
<Select
  value={model || ''}
  onChange={(e) => onModelChange && onModelChange(e.target.value)}
  disabled={disabled}
  options={[
    { value: '', label: loadingModels ? 'Loading models...' : 'Select a model...' },
    ...availableModels.map(m => {
      const details = modelDetails?.find(d => d.name === m);
      const isBlocked = (details as any)?.blocked_by_policy;
      return {
        value: m,
        label: isBlocked ? `🚫 ${m} (Blocked by IT)` : m,
        disabled: isBlocked
      };
    })
  ]}
  className="flex-1"
/>
```

Replace the `options={[...]}` expression with a call to the helper:

```tsx
<Select
  value={model || ''}
  onChange={(e) => onModelChange && onModelChange(e.target.value)}
  disabled={disabled}
  options={buildModelOptions({
    model,
    availableModels,
    modelDetails,
    loadingModels,
  })}
  className="flex-1"
/>
```

Leave all surrounding code (the endpoint selector above, the refresh button, the `modelDetails` info card below) untouched.

- [ ] **Step 3: Run typecheck**

Run from repo root:
```bash
cd packages/ui && npx tsc --noEmit
```

Expected output: no errors. (No output.)

- [ ] **Step 4: Run lint**

Run from repo root:
```bash
cd packages/ui && npm run lint
```

Expected output: no new warnings or errors attributable to `ModelCard.tsx` or the new test file. Pre-existing warnings elsewhere in the package are not this task's concern.

- [ ] **Step 5: Build the package to confirm the Vite/tsc build pipeline still succeeds**

Run from repo root:
```bash
cd packages/ui && npm run build
```

Expected output: successful build with no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/ui/src/components/llm/ModelCard.tsx \
        packages/ui/src/components/llm/__tests__/ModelCard.test.tsx
git commit -m "fix(ui): ModelCard shows saved model when availableModels list is empty"
```

---

### Task 3: Manual verification in the running dashboard

**Files:** none modified.

This is a human-in-the-loop check because the bug surfaces in specific runtime conditions (endpoint list not yet fetched) that the unit tests simulate but don't reproduce in a real browser.

- [ ] **Step 1: Start the dev environment**

Run from repo root:
```bash
scripts/dev.sh
```

Wait until the dashboard is reachable at `http://localhost:5174`.

- [ ] **Step 2: Reproduce the pre-fix condition**

Open the dashboard and navigate to AI Models settings. If Ollama is running and endpoints are reachable, temporarily stop Ollama (or disconnect from the cloud provider network) to simulate the empty `availableModels` state, then reload the page. This forces `handleFetchModels` to return `[]` for the saved endpoint.

- [ ] **Step 3: Verify the fix**

Confirm:
- Single / Fast Model dropdown shows the persisted model name (e.g., `qwen3:8b`), not `Select a model...`.
- Thinking Model and Code Model dropdowns behave the same.
- Clicking the refresh button next to a dropdown re-fetches; once the list loads, the synthetic entry disappears and the saved value remains selected.
- With Ollama back up and a clean page reload, the Models dropdowns look indistinguishable from the pre-fix happy path.

- [ ] **Step 4: Kill the dev environment**

Run from repo root:
```bash
scripts/dev.sh --kill
```

No commit for this task — it is verification only.

---

## Done criteria

1. `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` exists with the six `buildModelOptions` test cases and typechecks under `tsc --noEmit`.
2. `ModelCard.tsx` exports `buildModelOptions` and uses it inside the Model `<Select>` options prop. No inline options array remains in the component body.
3. `npm run build` succeeds for `@codrag/ui`.
4. Manual check: saved model renders in the dropdown even when the endpoint list is empty.

## Out of scope (do NOT do in this plan)

- Pipeline run gating when no models are configured.
- Auto-save of model selections (explicit "Set model scheme" flow is unchanged).
- `getSlotStatus` cleanup in `AIModelsSettings.tsx` (the "empty list → connected" badge behavior).
- Extracting `isSameModel` / `stripLatest` into a shared helper used by `AIModelsSettings.tsx`'s `modelInList`/`findRecommended`. That consolidation is a follow-up refactor.
