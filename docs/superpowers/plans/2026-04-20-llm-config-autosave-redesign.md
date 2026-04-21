# LLM Config Auto-Save Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Settings → AI Models auto-save every field except the Structured ↔ Assigned mode toggle, debounced at 1500 ms; keep mode toggle as an explicit "Apply … mode" button; hide the per-slot "Always available" checkbox on cloud endpoints.

**Architecture:** Three coordinated refactors. (1) A pure `createDebouncedSaver` factory in `packages/ui/src/lib/` is wrapped by a `useDebouncedAutoSave` hook in the dashboard; `useLLMConfig` uses it to persist `llm_config` after quiet periods and invoke `handleSwapModel` as a post-persist side effect. (2) `AIModelsSettings` loses its `configDirty`/`onSave` props, the combined Save button is relabelled to "Apply Structured/Assigned mode" and is tied exclusively to the mode draft; `App.tsx` provides an `onModeApply` that flushes any pending slot save before calling `handleModeSwitch`. (3) A shared `isLocalProvider` helper + a `showAlwaysOn` prop on `ModelCard` hide the VRAM-pinning checkbox on cloud slots.

**Tech Stack:** TypeScript, React 18, Vite. `@codrag/ui` and dashboard workspaces both use vitest-syntax tests that are currently type-checked via `tsc --noEmit` (no runtime runner wired); pure-logic helpers are the testability lever. Existing precedent: `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` (covers `buildModelOptions`). Follow the same style for every new test.

---

## File structure

**New files:**

- `packages/ui/src/lib/debouncedSaver.ts` — pure factory `createDebouncedSaver<T>({ onSave, delayMs, equals, onPersist })` returning `{ schedule(value), flush(), cancel() }`. No React.
- `packages/ui/src/lib/__tests__/debouncedSaver.test.ts` — pure-logic tests for the factory.
- `packages/ui/src/components/llm/provider-utils.ts` — `LOCAL_PROVIDERS` constant + `isLocalProvider(p)` predicate.
- `packages/ui/src/components/llm/__tests__/provider-utils.test.ts` — predicate tests.
- `packages/ui/src/components/llm/llmConfigHelpers.ts` — `stripModeFields(cfg)` helper used by the debounced-save change detector.
- `packages/ui/src/components/llm/__tests__/llmConfigHelpers.test.ts` — helper tests.
- `src/codrag/dashboard/src/hooks/useDebouncedAutoSave.ts` — thin React wrapper around `createDebouncedSaver`.

**Modified files:**

- `packages/ui/src/components/llm/ModelCard.tsx` — export pure helper `shouldShowAlwaysOn(...)`, add `showAlwaysOn?: boolean` prop, guard the "Always available" label with the helper.
- `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` — extend with four `shouldShowAlwaysOn` cases.
- `packages/ui/src/components/llm/AIModelsSettings.tsx` — drop `configDirty`/`onSave`, add `onModeApply`, relabel button, pass `showAlwaysOn` to the four slot cards.
- `src/codrag/dashboard/src/hooks/useLLMConfig.ts` — remove `llmConfigDirty` + `lastSavedRef` tracking + `saveLLMConfig`; add debounced auto-save wiring with `onSwapModel` option and `flushPendingSave` return.
- `src/codrag/dashboard/src/App.tsx` — remove `saveLLMConfig` wrapper, wire `onSwapModel` into `useLLMConfig`, add `handleModeApply` that flushes then calls `handleModeSwitch`.
- `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` — drop `configDirty`/`onSave` prop passthrough; add `onModeApply`.

---

## Task 1: `isLocalProvider` helper + tests

**Files:**
- Create: `packages/ui/src/components/llm/provider-utils.ts`
- Test: `packages/ui/src/components/llm/__tests__/provider-utils.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/llm/__tests__/provider-utils.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { isLocalProvider, LOCAL_PROVIDERS } from '../provider-utils';

describe('isLocalProvider', () => {
  it('returns true for ollama', () => {
    expect(isLocalProvider('ollama')).toBe(true);
  });

  it('returns true for lm-studio', () => {
    expect(isLocalProvider('lm-studio')).toBe(true);
  });

  it('returns false for openai', () => {
    expect(isLocalProvider('openai')).toBe(false);
  });

  it('returns false for anthropic', () => {
    expect(isLocalProvider('anthropic')).toBe(false);
  });

  it('returns false for google', () => {
    expect(isLocalProvider('google')).toBe(false);
  });

  it('returns false for openai-compatible', () => {
    expect(isLocalProvider('openai-compatible')).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isLocalProvider(undefined)).toBe(false);
  });
});

describe('LOCAL_PROVIDERS', () => {
  it('contains exactly ollama and lm-studio', () => {
    expect([...LOCAL_PROVIDERS].sort()).toEqual(['lm-studio', 'ollama']);
  });
});
```

- [ ] **Step 2: Verify test fails typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: FAIL — `Cannot find module '../provider-utils'`.

- [ ] **Step 3: Implement the helper**

Create `packages/ui/src/components/llm/provider-utils.ts`:

```ts
import type { LLMProvider } from '../../types';

export const LOCAL_PROVIDERS: readonly LLMProvider[] = ['ollama', 'lm-studio'] as const;

export function isLocalProvider(p: LLMProvider | undefined): boolean {
  return !!p && (LOCAL_PROVIDERS as readonly string[]).includes(p);
}
```

- [ ] **Step 4: Verify typecheck passes**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS (exit 0, no output).

- [ ] **Step 5: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add packages/ui/src/components/llm/provider-utils.ts packages/ui/src/components/llm/__tests__/provider-utils.test.ts
git -c commit.gpgsign=false commit -m "feat(ui): add isLocalProvider helper"
```

---

## Task 2: `shouldShowAlwaysOn` helper + ModelCard prop

**Files:**
- Modify: `packages/ui/src/components/llm/ModelCard.tsx` (add prop + helper, guard the label)
- Modify: `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` (extend with 4 cases)

- [ ] **Step 1: Write the failing tests**

Append to `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` (after the existing `describe('buildModelOptions', …)` block):

```ts
import { shouldShowAlwaysOn } from '../ModelCard';

describe('shouldShowAlwaysOn', () => {
  it('returns true when showAlwaysOn=true and handler provided', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: true, onAlwaysOnChange: () => {} })).toBe(true);
  });

  it('returns false when showAlwaysOn=false even if handler provided', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: false, onAlwaysOnChange: () => {} })).toBe(false);
  });

  it('defaults to true when showAlwaysOn is undefined and handler provided (backcompat)', () => {
    expect(shouldShowAlwaysOn({ onAlwaysOnChange: () => {} })).toBe(true);
  });

  it('returns false when no handler regardless of showAlwaysOn', () => {
    expect(shouldShowAlwaysOn({ showAlwaysOn: true })).toBe(false);
  });
});
```

- [ ] **Step 2: Verify test fails typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: FAIL — `Module './ModelCard' has no exported member 'shouldShowAlwaysOn'`.

- [ ] **Step 3: Add the helper + prop + guard to `ModelCard.tsx`**

In `packages/ui/src/components/llm/ModelCard.tsx`:

3a. **Add the pure helper** (export it so tests can import). Place it just above the component function definition, near the other exported helpers like `buildModelOptions`:

```ts
export function shouldShowAlwaysOn({
  showAlwaysOn,
  onAlwaysOnChange,
}: {
  showAlwaysOn?: boolean;
  onAlwaysOnChange?: (v: boolean) => void;
}): boolean {
  return (showAlwaysOn ?? true) && onAlwaysOnChange !== undefined;
}
```

3b. **Add the prop to the `ModelCardProps` interface** (sibling of the existing `alwaysOn` / `onAlwaysOnChange` block near line 48):

```ts
  // Always on (keep loaded)
  alwaysOn?: boolean;
  onAlwaysOnChange?: (alwaysOn: boolean) => void;
  /** Show the "Always available (Keep loaded)" checkbox. Defaults to true.
   *  Callers should pass false for cloud endpoints (VRAM pinning is meaningless there). */
  showAlwaysOn?: boolean;
```

3c. **Add the prop to the destructured component params** (near line 162):

```ts
  alwaysOn = false,
  onAlwaysOnChange,
  showAlwaysOn,
```

3d. **Replace the current guard** at line 337:

Change:
```tsx
{onAlwaysOnChange !== undefined && (
  <label className={cn(
```

To:
```tsx
{shouldShowAlwaysOn({ showAlwaysOn, onAlwaysOnChange }) && (
  <label className={cn(
```

- [ ] **Step 4: Verify typecheck passes**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add packages/ui/src/components/llm/ModelCard.tsx packages/ui/src/components/llm/__tests__/ModelCard.test.tsx
git -c commit.gpgsign=false commit -m "feat(ui): ModelCard gains showAlwaysOn prop + shouldShowAlwaysOn helper"
```

---

## Task 3: `stripModeFields` helper + tests

**Files:**
- Create: `packages/ui/src/components/llm/llmConfigHelpers.ts`
- Test: `packages/ui/src/components/llm/__tests__/llmConfigHelpers.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/llm/__tests__/llmConfigHelpers.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { stripModeFields } from '../llmConfigHelpers';
import type { LLMConfig } from '../../../types';

const baseConfig: LLMConfig = {
  saved_endpoints: [],
  embedding: { source: 'endpoint', endpoint_id: 'e', model: 'nomic-embed-text' },
  small_model: { enabled: true, endpoint_id: 'e', model: 'qwen3:8b' },
  large_model: { enabled: false },
  code_model: { enabled: false },
  assignment_mode: 'structured',
  assignment_blocks: [
    { id: 'b1', endpoint_id: 'e', model: 'qwen3:8b', tasks: [] },
  ],
};

describe('stripModeFields', () => {
  it('removes assignment_mode', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_mode' in out).toBe(false);
  });

  it('removes assignment_blocks', () => {
    const out = stripModeFields(baseConfig);
    expect('assignment_blocks' in out).toBe(false);
  });

  it('preserves non-mode fields', () => {
    const out = stripModeFields(baseConfig);
    expect(out.small_model).toEqual(baseConfig.small_model);
    expect(out.embedding).toEqual(baseConfig.embedding);
    expect(out.saved_endpoints).toEqual(baseConfig.saved_endpoints);
  });

  it('does not mutate the input', () => {
    const snapshot = JSON.stringify(baseConfig);
    stripModeFields(baseConfig);
    expect(JSON.stringify(baseConfig)).toBe(snapshot);
  });
});
```

- [ ] **Step 2: Verify test fails typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: FAIL — `Cannot find module '../llmConfigHelpers'`.

- [ ] **Step 3: Implement the helper**

Create `packages/ui/src/components/llm/llmConfigHelpers.ts`:

```ts
import type { LLMConfig } from '../../types';

/** Return a shallow copy of the LLM config with mode-owned fields removed.
 *  Used by the debounced auto-save layer for change detection: mutations to
 *  `assignment_mode` or `assignment_blocks` are committed via the explicit
 *  "Apply mode" button path, not via auto-save. */
export function stripModeFields(cfg: LLMConfig): Omit<LLMConfig, 'assignment_mode' | 'assignment_blocks'> {
  const { assignment_mode: _m, assignment_blocks: _b, ...rest } = cfg;
  void _m;
  void _b;
  return rest;
}
```

- [ ] **Step 4: Verify typecheck passes**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add packages/ui/src/components/llm/llmConfigHelpers.ts packages/ui/src/components/llm/__tests__/llmConfigHelpers.test.ts
git -c commit.gpgsign=false commit -m "feat(ui): add stripModeFields helper for auto-save change detection"
```

---

## Task 4: Pure `createDebouncedSaver` factory + tests

**Files:**
- Create: `packages/ui/src/lib/debouncedSaver.ts`
- Test: `packages/ui/src/lib/__tests__/debouncedSaver.test.ts`

Note: `packages/ui/src/lib/` already exists (contains `utils.ts`). The `__tests__` subfolder does not yet — create it.

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/lib/__tests__/debouncedSaver.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createDebouncedSaver } from '../debouncedSaver';

describe('createDebouncedSaver', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fire before any schedule() call', () => {
    const onSave = vi.fn();
    createDebouncedSaver<number>({ onSave, delayMs: 100 });
    vi.advanceTimersByTime(1000);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('fires once after delayMs of quiet', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    expect(onSave).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(100);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith(1);
  });

  it('coalesces rapid schedules into one save with the latest value', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    await vi.advanceTimersByTimeAsync(50);
    saver.schedule(2);
    await vi.advanceTimersByTimeAsync(50);
    saver.schedule(3);
    await vi.advanceTimersByTimeAsync(100);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith(3);
  });

  it('flush() forces immediate save and resolves after onPersist', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onPersist = vi.fn();
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 10000, onPersist });
    saver.schedule(42);
    expect(onSave).not.toHaveBeenCalled();
    await saver.flush();
    expect(onSave).toHaveBeenCalledWith(42);
    expect(onPersist).toHaveBeenCalledWith(42);
  });

  it('flush() is a no-op when nothing is pending', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    await saver.flush();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('cancel() discards any pending save', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 100 });
    saver.schedule(1);
    saver.cancel();
    await vi.advanceTimersByTimeAsync(200);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('skips save when scheduled value equals the last persisted value', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const saver = createDebouncedSaver<{ v: number }>({ onSave, delayMs: 50 });
    saver.schedule({ v: 1 });
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
    saver.schedule({ v: 1 });
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('uses custom equals when provided', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const equals = vi.fn().mockReturnValue(true);
    const saver = createDebouncedSaver<number>({ onSave, delayMs: 50, equals });
    saver.schedule(1);
    await vi.advanceTimersByTimeAsync(50);
    expect(onSave).toHaveBeenCalledTimes(1);
    saver.schedule(2);
    await vi.advanceTimersByTimeAsync(50);
    expect(equals).toHaveBeenCalledWith(1, 2);
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Verify test fails typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: FAIL — `Cannot find module '../debouncedSaver'`.

- [ ] **Step 3: Implement the factory**

Create `packages/ui/src/lib/debouncedSaver.ts`:

```ts
export interface DebouncedSaverOptions<T> {
  onSave: (value: T) => Promise<void> | void;
  delayMs: number;
  /** Fired synchronously after onSave resolves. */
  onPersist?: (value: T) => void;
  /** Equality test; defaults to JSON.stringify comparison. */
  equals?: (a: T, b: T) => boolean;
}

export interface DebouncedSaver<T> {
  /** Schedule a save; trailing-edge coalescing. */
  schedule(value: T): void;
  /** Force any pending save to run immediately; resolves after onPersist. */
  flush(): Promise<void>;
  /** Discard any pending save without firing. */
  cancel(): void;
}

export function createDebouncedSaver<T>(opts: DebouncedSaverOptions<T>): DebouncedSaver<T> {
  const equals = opts.equals ?? ((a: T, b: T) => JSON.stringify(a) === JSON.stringify(b));
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: { value: T } | null = null;
  let lastPersisted: { value: T } | null = null;

  const runSave = async (): Promise<void> => {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    if (!pending) return;
    const { value } = pending;
    pending = null;
    if (lastPersisted && equals(lastPersisted.value, value)) return;
    await opts.onSave(value);
    lastPersisted = { value };
    opts.onPersist?.(value);
  };

  return {
    schedule(value: T): void {
      pending = { value };
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => {
        void runSave();
      }, opts.delayMs);
    },
    async flush(): Promise<void> {
      await runSave();
    },
    cancel(): void {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      pending = null;
    },
  };
}
```

- [ ] **Step 4: Verify typecheck passes**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add packages/ui/src/lib/debouncedSaver.ts packages/ui/src/lib/__tests__/debouncedSaver.test.ts
git -c commit.gpgsign=false commit -m "feat(ui): add createDebouncedSaver factory"
```

---

## Task 5: `useDebouncedAutoSave` React hook

**Files:**
- Create: `src/codrag/dashboard/src/hooks/useDebouncedAutoSave.ts`

No test (thin wrapper — the logic lives in `createDebouncedSaver` which is already covered). `tsc` validates the wiring.

- [ ] **Step 1: Implement the hook**

Create `src/codrag/dashboard/src/hooks/useDebouncedAutoSave.ts`:

```ts
import { useEffect, useMemo, useRef } from 'react'
import { createDebouncedSaver, type DebouncedSaver } from '@prep/ui/lib/debouncedSaver'

export interface UseDebouncedAutoSaveOptions<T> {
  value: T
  onSave: (value: T) => Promise<void> | void
  delayMs?: number
  onPersist?: (value: T) => void
  equals?: (a: T, b: T) => boolean
  /** When false, schedule/flush are suppressed. Flip to true after initial hydrate. */
  enabled?: boolean
}

export interface UseDebouncedAutoSaveResult {
  flush: () => Promise<void>
}

/** Schedules a trailing-edge debounced save whenever `value` changes.
 *  Flushes any pending save synchronously on unmount. */
export function useDebouncedAutoSave<T>(opts: UseDebouncedAutoSaveOptions<T>): UseDebouncedAutoSaveResult {
  const { value, enabled = true, delayMs = 1500 } = opts

  // Stable refs for callbacks so the saver identity doesn't change every render.
  const onSaveRef = useRef(opts.onSave)
  onSaveRef.current = opts.onSave
  const onPersistRef = useRef(opts.onPersist)
  onPersistRef.current = opts.onPersist
  const equalsRef = useRef(opts.equals)
  equalsRef.current = opts.equals

  const saver: DebouncedSaver<T> = useMemo(
    () =>
      createDebouncedSaver<T>({
        onSave: (v) => onSaveRef.current(v),
        delayMs,
        onPersist: (v) => onPersistRef.current?.(v),
        equals: equalsRef.current ? (a, b) => equalsRef.current!(a, b) : undefined,
      }),
    [delayMs],
  )

  // Track whether we've seen the first enabled render so we can baseline.
  const hydratedRef = useRef(false)
  useEffect(() => {
    if (!enabled) return
    if (!hydratedRef.current) {
      hydratedRef.current = true
      return // baseline: don't save the initial value
    }
    saver.schedule(value)
  }, [value, enabled, saver])

  // Flush on unmount.
  useEffect(() => {
    return () => {
      void saver.flush()
    }
  }, [saver])

  return {
    flush: () => saver.flush(),
  }
}
```

- [ ] **Step 2: Verify typecheck passes**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Verify the `@codrag/ui/lib/debouncedSaver` import path resolves**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && grep -r "'@codrag/ui/" packages/ui/vite.config.ts src/codrag/dashboard/vite.config.ts | head -5`
Expected: see the sub-path alias rule `{ find: /^@codrag\/ui\/(.*)$/, replacement: \`${uiSrcPath}/$1\` }` in `src/codrag/dashboard/vite.config.ts`. The import path `@codrag/ui/lib/debouncedSaver` will resolve to `packages/ui/src/lib/debouncedSaver.ts`.

If the subpath isn't exposed by `packages/ui/package.json` exports, add a re-export instead: append to `packages/ui/src/index.ts`:

```ts
export { createDebouncedSaver, type DebouncedSaver, type DebouncedSaverOptions } from './lib/debouncedSaver';
```

And change the hook import to:

```ts
import { createDebouncedSaver, type DebouncedSaver } from '@prep/ui'
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add src/codrag/dashboard/src/hooks/useDebouncedAutoSave.ts
# Also the re-export if it was needed:
git add packages/ui/src/index.ts 2>/dev/null || true
git -c commit.gpgsign=false commit -m "feat(dashboard): add useDebouncedAutoSave hook"
```

---

## Task 6: Rewire `useLLMConfig` to auto-save

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useLLMConfig.ts`

This is the load-bearing change. Read the current file before editing (`src/codrag/dashboard/src/hooks/useLLMConfig.ts`) to match the surrounding style. No tests (no runtime runner); manual verification comes in Task 9.

- [ ] **Step 1: Remove the explicit-save infrastructure**

Delete the following from `useLLMConfig.ts`:

1. The `llmConfigDirty` state and its `useEffect` (currently lines 247–280 — the block starting with the comment `// ── Explicit save (no auto-save) ────────────` through the dirty-tracking `useEffect`).
2. The `saveLLMConfig` function (currently lines 282–292).
3. The embedding-only auto-save inside `handleLLMConfigChange` (the `if (JSON.stringify(prev.embedding) !== JSON.stringify(cfg.embedding))` block at lines 68–70). Replace the function body with:

```ts
const handleLLMConfigChange = useCallback((cfg: LLMConfig) => {
  setLLMConfig(cfg)
  onDirtyRef.current?.()
}, [])
```

(No more `api` dep; the auto-save layer handles persistence.)

4. Drop `llmConfigDirty` and `saveLLMConfig` from the return object.

- [ ] **Step 2: Widen the hook's option surface**

Change the `UseLLMConfigOptions` interface (line ~12):

```ts
interface UseLLMConfigOptions {
  onDirty?: () => void
  /** Fired after a successful auto-save persist. Typically wired to handleSwapModel. */
  onSwapModel?: () => void
}
```

Capture it on a ref at the top of the hook, next to `onDirtyRef`:

```ts
const onSwapModelRef = useRef(onSwapModel)
onSwapModelRef.current = onSwapModel
```

And add `onSwapModel` to the destructured options.

- [ ] **Step 3: Wire the debounced auto-save**

Import at the top:

```ts
import { useDebouncedAutoSave } from './useDebouncedAutoSave'
import { stripModeFields } from '@prep/ui/components/llm/llmConfigHelpers'
```

(If subpath imports aren't exported, re-export `stripModeFields` from `packages/ui/src/index.ts` the same way as Task 5 Step 3, and import from `'@codrag/ui'` instead.)

Add an `enabled` gate and the auto-save hook. Place this block after the endpoint/model handlers and before the `markLLMConfigClean` definition:

```ts
// Gate auto-save until the backend config has been loaded and markLLMConfigClean() has run.
const [autoSaveEnabled, setAutoSaveEnabled] = useState(false)

// Trailing-edge debounced persist of the full LLM config (minus mode-owned fields,
// which are committed via the explicit "Apply mode" button path).
const saveValue = useMemo(() => stripModeFields(llmConfig), [llmConfig])
const { flush: flushPendingSave } = useDebouncedAutoSave({
  value: saveValue,
  enabled: autoSaveEnabled,
  delayMs: 1500,
  onSave: async () => {
    try {
      await api.updateGlobalConfig({ llm_config: llmConfig })
    } catch {
      // Silent fail — matches legacy policy. User can retry by editing again.
    }
  },
  onPersist: () => {
    onSwapModelRef.current?.()
    void fetchLLMSlotsStatus()
  },
})
```

Notes for the implementer:

- `onSave` calls `updateGlobalConfig` with the full `llmConfig` (not the stripped version). The stripped value is the *change-detection* input; the backend still receives the complete config.
- Adding `useState` and `useMemo` requires updating the `import` line at the top of the file. Current:

  ```ts
  import { useState, useCallback, useEffect, useRef } from 'react'
  ```

  Change to:

  ```ts
  import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
  ```

- [ ] **Step 4: Update `markLLMConfigClean` to enable auto-save**

Replace the current implementation:

```ts
const markLLMConfigClean = useCallback(() => {
  lastSavedRef.current = JSON.stringify(llmConfig)
  setLlmConfigDirty(false)
}, [llmConfig])
```

With:

```ts
const markLLMConfigClean = useCallback(() => {
  setAutoSaveEnabled(true)
}, [])
```

(The `lastSavedRef` is gone; `useDebouncedAutoSave` does baseline tracking internally via its first-enabled-render hook.)

- [ ] **Step 5: Update the return object**

The hook's return block should now expose `flushPendingSave` and drop `llmConfigDirty` / `saveLLMConfig`:

```ts
return {
  llmConfig,
  setLLMConfig,
  availableModels,
  modelDetails,
  loadingModels,
  testingSlot,
  testResults,
  llmSlotsStatus,
  handleLLMConfigChange,
  handleAddEndpoint,
  handleEditEndpoint,
  handleDeleteEndpoint,
  handleTestEndpoint,
  handleFetchModels,
  handleTestModel,
  handleClearTestResult,
  handleDownloadModel,
  handleModeSwitch,
  markLLMConfigClean,
  fetchLLMSlotsStatus,
  flushPendingSave,
}
```

- [ ] **Step 6: Verify typecheck passes**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: PASS. The consumers in `App.tsx` / `useDashboardPanels.tsx` will error on the removed `llmConfigDirty` / `saveLLMConfig` properties — that's intentional; those are fixed in Tasks 7 and 8.

- [ ] **Step 7: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add src/codrag/dashboard/src/hooks/useLLMConfig.ts
# If stripModeFields needed a re-export from @codrag/ui/index.ts:
git add packages/ui/src/index.ts 2>/dev/null || true
git -c commit.gpgsign=false commit -m "feat(dashboard): useLLMConfig debounced auto-save"
```

Note: typecheck will still fail until Tasks 7 + 8 land. Commit here because this is a complete logical unit.

---

## Task 7: Wire `onSwapModel` + `onModeApply` in `App.tsx`

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Remove the `saveLLMConfig` wrapper**

Delete lines 481–487 in `src/codrag/dashboard/src/App.tsx` (the block that starts with `// Wrap saveLLMConfig to also trigger model swap for running pipelines` and includes `const saveLLMConfig = useCallback(async () => { … }, […])`).

- [ ] **Step 2: Rename `_rawSaveLLMConfig` removal + pass `onSwapModel`**

The `useLLMConfig` destructure currently ends with:

```ts
saveLLMConfig: _rawSaveLLMConfig, markLLMConfigClean,
```

Replace with:

```ts
markLLMConfigClean, flushPendingSave,
```

And change the `useLLMConfig` call site:

```ts
} = useLLMConfig({ onDirty: () => setConfigDirty(true) })
```

to:

```ts
} = useLLMConfig({
  onDirty: () => setConfigDirty(true),
  onSwapModel: handleSwapModel,
})
```

**Ordering caveat:** `handleSwapModel` comes from `useEnrichment` (destructured earlier, around line 367). Confirm `useEnrichment` runs before `useLLMConfig` in the function body. It does per the existing file — if not, reorder the destructures so `handleSwapModel` is declared first.

- [ ] **Step 3: Add `handleModeApply`**

Find the `handleModeSwitch` call site in `App.tsx` (grep for `handleModeSwitch` — it's threaded through to `useDashboardPanels` as `onModeSwitch`). Add a sibling callback just above it:

```ts
const handleModeApply = useCallback(async (mode: AssignmentMode, blocks?: LLMConfig['assignment_blocks']) => {
  // Commit any pending debounced slot save so the mode switch sees the latest config.
  await flushPendingSave()
  await handleModeSwitch(mode, blocks)
}, [flushPendingSave, handleModeSwitch])
```

If `AssignmentMode` and `LLMConfig` aren't already imported from `@codrag/ui`, add them. Check the existing imports at the top of `App.tsx`.

- [ ] **Step 4: Drop the `saveLLMConfig` from consumers**

Search the rest of `App.tsx` for `saveLLMConfig`. Any remaining references must be removed or replaced (there shouldn't be any — it was only used via the panel prop). Also confirm no other file in `src/codrag/dashboard/src/` references the old name: 

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
grep -rn "saveLLMConfig" src/codrag/dashboard/src/ packages/ui/src/
```

Expected: only hits inside `useDashboardPanels.tsx` (which Task 8 fixes).

- [ ] **Step 5: Verify typecheck** (expect one remaining error — `useDashboardPanels.tsx`)

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: single error in `useDashboardPanels.tsx` re: `p.saveLLMConfig` / `p.llmConfigDirty`. That's Task 8.

- [ ] **Step 6: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add src/codrag/dashboard/src/App.tsx
git -c commit.gpgsign=false commit -m "feat(dashboard): App wires onSwapModel + handleModeApply"
```

---

## Task 8: `AIModelsSettings` + `useDashboardPanels` prop surgery

**Files:**
- Modify: `packages/ui/src/components/llm/AIModelsSettings.tsx`
- Modify: `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`

- [ ] **Step 1: Update `AIModelsSettings` props interface**

In `packages/ui/src/components/llm/AIModelsSettings.tsx` (lines 78–81), replace:

```ts
  // Explicit save (P48-F26): config changes are local until Save is clicked
  configDirty?: boolean;
  onSave?: () => void;
```

With:

```ts
  /** Fires when the user clicks "Apply [Structured|Assigned] mode".
   *  Consumers should flush any pending debounced save, then call switchAssignmentMode. */
  onModeApply?: (mode: AssignmentMode, blocks?: LLMConfig['assignment_blocks']) => Promise<void> | void;
```

Update the component destructure at lines 376–378 — remove `configDirty`, `onSave` and add `onModeApply`:

```ts
  adminPolicy,
  onModeApply,
}: AIModelsSettingsProps) {
```

- [ ] **Step 2: Remove `handleModeSave`; update the button**

Delete the `handleModeSave` `useCallback` at lines 389–399.

Replace the button block at lines 746–761:

```tsx
<button
  onClick={async () => {
    if (isDraftDirty) await handleModeSave();
    if (configDirty && onSave) onSave();
  }}
  disabled={!isDraftDirty && !configDirty}
  className={cn(
    'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
    (isDraftDirty || configDirty)
      ? 'bg-primary text-surface hover:bg-primary/90 shadow-sm'
      : 'bg-transparent text-text-muted cursor-not-allowed opacity-50'
  )}
>
  <Save className="w-3.5 h-3.5" />
  Set model scheme
</button>
```

With:

```tsx
<button
  onClick={async () => {
    if (!isDraftDirty) return;
    const newBlocks =
      draftMode === 'mapped' && (config.assignment_blocks?.length ?? 0) === 0
        ? [{ id: `block-${Date.now()}`, endpoint_id: '', model: '', tasks: [] }]
        : (config.assignment_blocks ?? []);
    await onModeApply?.(draftMode, newBlocks);
  }}
  disabled={!isDraftDirty}
  className={cn(
    'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
    isDraftDirty
      ? 'bg-primary text-surface hover:bg-primary/90 shadow-sm'
      : 'bg-transparent text-text-muted cursor-not-allowed opacity-50'
  )}
>
  <Save className="w-3.5 h-3.5" />
  Apply {draftMode === 'structured' ? 'Structured' : 'Assigned'} mode
</button>
```

- [ ] **Step 3: Pass `showAlwaysOn` to the four slot cards**

Add a helper just inside the component function (next to the existing `modelInList` usage — right after the props destructure and `savedMode` derivation):

```ts
const endpointProviderFor = (endpointId: string | undefined) =>
  config.saved_endpoints.find((e) => e.id === endpointId)?.provider;
```

Add the import at the top of the file (next to other `./` imports):

```ts
import { isLocalProvider } from './provider-utils';
```

In each of the four `<ModelCard>` renders, add `showAlwaysOn={isLocalProvider(endpointProviderFor(<slotEndpointId>))}` alongside the existing `alwaysOn=` prop:

- **Single/Fast** (lines ~810–835): after `onAlwaysOnChange={handleSmallAlwaysOnChange}` add
  ```tsx
  showAlwaysOn={isLocalProvider(endpointProviderFor(config.small_model.endpoint_id))}
  ```
- **Code** (lines ~838–864): after `onAlwaysOnChange={handleCodeAlwaysOnChange}` add
  ```tsx
  showAlwaysOn={isLocalProvider(endpointProviderFor(config.code_model?.endpoint_id))}
  ```
- **Thinking** (lines ~867–892): after `onAlwaysOnChange={handleLargeAlwaysOnChange}` add
  ```tsx
  showAlwaysOn={isLocalProvider(endpointProviderFor(config.large_model.endpoint_id))}
  ```
- **Swarm Coordinator** (lines ~903–929): after `onAlwaysOnChange={handleCoordinatorAlwaysOnChange}` add
  ```tsx
  showAlwaysOn={isLocalProvider(endpointProviderFor(coordinatorSlot.endpoint_id))}
  ```

- [ ] **Step 4: Update `useDashboardPanels.tsx` prop passthrough**

In `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`, lines 1259–1261:

Replace:
```tsx
configDirty={p.llmConfigDirty}
onSave={p.saveLLMConfig}
onModeSwitch={p.handleModeSwitch}
```

With:
```tsx
onModeApply={p.handleModeApply}
onModeSwitch={p.handleModeSwitch}
```

(Keep `onModeSwitch` — it's still used by `useLLMConfig.handleModeSwitch`. `onModeApply` is the button-path wrapper that flushes first.)

Trace the panel props object (`p`) backward to where it's constructed (likely the `useDashboardPanels` hook's caller in `App.tsx`). Drop `llmConfigDirty` / `saveLLMConfig` from the object literal and add `handleModeApply: handleModeApply` (the function defined in Task 7 Step 3). Do not leave unused `llmConfigDirty` consumer code — delete it.

- [ ] **Step 5: Verify typecheck passes (repo-wide)**

Run both:

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui && npm run typecheck
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/dashboard && npx tsc --noEmit
```

Expected: PASS for both.

- [ ] **Step 6: Verify build**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run build --workspace=@codrag/ui`
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
git add packages/ui/src/components/llm/AIModelsSettings.tsx src/codrag/dashboard/src/hooks/useDashboardPanels.tsx src/codrag/dashboard/src/App.tsx
git -c commit.gpgsign=false commit -m "feat(ui): AIModelsSettings auto-save; 'Apply mode' button; cloud hides always-available"
```

---

## Task 9: Manual browser verification

**Files:** none modified.

Auto-save is impossible to validate from `tsc` alone; this task exercises the golden path in the running dashboard.

- [ ] **Step 1: Start the dev environment**

```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG
scripts/dev.sh
```

Wait for:
- daemon on :8400
- dashboard on http://localhost:5174
- no errors in the terminal output

- [ ] **Step 2: Verify auto-save of slot changes**

1. Open http://localhost:5174 → Settings → AI Models.
2. Under **Single / Fast Model**, switch the model to a different value via the dropdown.
3. Wait ~2 s.
4. Open the browser DevTools Network tab; confirm exactly one `PATCH /api/global-config` (or `POST`, whichever the client uses) request fires with the new `llm_config.small_model.model`.
5. Refresh the page. Confirm the new selection is still shown.

- [ ] **Step 3: Verify debounce coalesces rapid edits**

1. On the Single/Fast card, change the model three times in quick succession (under 1.5 s between clicks).
2. Wait ~2 s.
3. Network tab: confirm exactly **one** save request fired, containing the final value.

- [ ] **Step 4: Verify mid-run behaviour**

1. Start a pipeline (any project, Fast or Deep Enrichment group).
2. While it's running, change the Single/Fast model.
3. Wait ~2 s.
4. Network tab: confirm one `global-config` save **and** one `POST /api/projects/<id>/pipeline/swap-model` request. The pipeline should briefly pause and resume.

- [ ] **Step 5: Verify "Apply mode" button**

1. Click **Assigned** in the mode toggle. The button label should change to "Apply Assigned mode" and become enabled (primary style).
2. Click it. Network tab: confirm `POST /api/llm/assignment-mode` (or whatever `switchAssignmentMode` calls) fires.
3. Click **Structured** again without saving. Confirm the button shows "Apply Structured mode" and is enabled.
4. Click it. Confirm the mode persists across page reload.

- [ ] **Step 6: Verify cloud hides the Always Available checkbox**

1. In Endpoint Manager, add a cloud endpoint (e.g. an OpenAI-compatible one).
2. On the Single/Fast card, switch the endpoint to the cloud one.
3. Confirm the "Always available (Keep loaded)" checkbox **disappears**.
4. Switch the endpoint back to Ollama. Confirm the checkbox **reappears**.

- [ ] **Step 7: Verify no false dirty state on initial load**

1. Hard-reload the dashboard.
2. Within the first ~2 s after connection, open the Network tab.
3. Confirm **no** `global-config` save fires before the user interacts with anything.

- [ ] **Step 8: Report findings**

If any step fails, capture the symptom, identify the contributing task (1–8), and return to that task for a fix. If all steps pass, mark this task complete.

---

## Done criteria

All of the following are true:

- [x] Tasks 1–8 are committed.
- [x] `cd packages/ui && npm run typecheck` exits 0.
- [x] `cd src/codrag/dashboard && npx tsc --noEmit` exits 0.
- [x] `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run build --workspace=@codrag/ui` succeeds.
- [x] Task 9 manual verification steps 2–7 pass.
- [x] No remaining references to `saveLLMConfig`, `llmConfigDirty`, `configDirty` (as a prop on `AIModelsSettings`), or "Set model scheme" string in the changed files.
