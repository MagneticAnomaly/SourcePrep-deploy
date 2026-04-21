# LLM config auto-save redesign

## Problem

Settings → AI Models currently behaves inconsistently:

- **Auto-saves:** embedding slot, saved endpoints (add/edit/delete).
- **Requires clicking "Set model scheme":** Single/Fast, Thinking, Code, Coordinator model slots; `always_on` per slot; `assignment_blocks`; `advanced` settings (`enforce_cloud_token_safety`, `max_thinking_budget`); and the Structured ↔ Assigned mode toggle itself.

The mixed model produces a surprising failure mode: the user changes a model, doesn't realise a Save step is required, and the "real" configured model drifts away from what the UI shows. The one-button "Set model scheme" couples two very different operations — per-slot edits and a full mode restructure — into the same gesture.

Separately, the per-slot **Always available (Keep loaded)** checkbox drives VRAM-thrashing protection. It is meaningful only for local providers that hold a model in GPU memory (`ollama`, `lm-studio`). Cloud providers (`openai`, `anthropic`, `google`, `openai-compatible`) do not own VRAM, so the checkbox is visual noise on those slots and has no effect.

## Fix (summary)

Three bundled changes to `AIModelsSettings` and `useLLMConfig`:

1. **Auto-save everything except the mode toggle.** Slot edits, `always_on`, `assignment_blocks`, and `advanced` settings persist to the backend automatically after a 1500 ms debounce. Save triggers the existing `swap_model` pause→resume cycle for running pipeline groups (unchanged behaviour — only its invocation moves into the debounced path).
2. **Mode toggle stays explicit.** Clicking Structured / Assigned only changes the draft UI state. A relabelled button ("Apply Structured mode" / "Apply Assigned mode") commits the switch via `switchAssignmentMode`. Disabled unless the draft differs from the saved mode.
3. **Hide "Always available" checkbox for cloud endpoints.** Shown only when the slot's endpoint has `provider ∈ { 'ollama', 'lm-studio' }`.

## Goals

- Users never lose a model selection because they forgot to click Save.
- A rapid flurry of edits collapses into one backend write + one `swap_model` per settled edit.
- The mode toggle remains a deliberate, confirmed action — switching between Structured and Assigned restructures all slot assignments and deserves an explicit commit.
- Cloud slots do not display controls that have no effect for them.

## Non-goals

- Pipeline run gating when no model is configured (backend already refuses; out of scope).
- Display-regression fix for saved model names (`buildModelOptions`) shipped earlier and is unchanged.
- Extraction of `modelInList` / `buildModelOptions` / `matchesSaved` into a shared helper.
- `getSlotStatus` cleanup (the "empty availableModels → connected" fallback).
- Toast / banner UI for auto-save failures. Failures stay silent; existing sidebar AI Gateway status indicator surfaces endpoint health.
- Visual changes to the Structured / Assigned toggle beyond relabelling the Save button.

## Behavioural acceptance

- Selecting a model in any slot, changing `always_on`, editing an assignment block, or toggling an Advanced setting updates local state immediately and persists to the backend after 1500 ms of inactivity. No button click required.
- If a pipeline group is running, the auto-save path calls `handleSwapModel()` after the persist resolves. Rapid edits produce a single swap after the debounce settles.
- Clicking the Structured / Assigned tabs changes only the in-memory draft mode; the button enables. The button label reads "Apply Structured mode" or "Apply Assigned mode" based on the current draft. Clicking it flushes any pending debounced slot save, then calls `switchAssignmentMode(draftMode, blocks)`.
- On the Embedding and model-slot cards, the "Always available (Keep loaded)" checkbox appears only when the card's endpoint is provided by `ollama` or `lm-studio`. Cloud endpoints (`openai`, `anthropic`, `google`, `openai-compatible`) do not render the checkbox.
- On initial load, the backend config is fetched, applied to local state, and marked clean — no spurious auto-save fires before the user changes anything.

## Architecture

### New hook: `useDebouncedAutoSave`

File: `src/prep/dashboard/src/hooks/useDebouncedAutoSave.ts`

Interface:

```ts
interface Options<T> {
  value: T
  onSave: (value: T) => Promise<void> | void
  delayMs?: number                  // default 1500
  onPersist?: (value: T) => void    // fires after onSave resolves
  equals?: (a: T, b: T) => boolean  // default: deep equality via JSON.stringify
  enabled?: boolean                 // default true; set false to suppress before initial load
}
function useDebouncedAutoSave<T>(opts: Options<T>): { flush: () => Promise<void> }
```

Behaviour:

- Does not fire before the first change. A serialised baseline (`lastSavedRef`) is captured on first enable; equality with the baseline short-circuits save.
- Trailing-edge only: each change resets the timer. Only the last value survives.
- On unmount, flushes any pending save synchronously (does not block unmount on the resolve).
- `flush()` forces immediate save and resolves after `onPersist` runs. Used by the mode-apply path so mode switches see any pending slot edit already committed.
- `enabled=false` suppresses all scheduling. Toggling back to `true` re-captures the baseline from the current value (so "re-enable" is not treated as a dirty change).

### Refactor: `useLLMConfig`

File: `src/prep/dashboard/src/hooks/useLLMConfig.ts`

**Remove:**

- The `llmConfigDirty` state and the tracking `useEffect` that compared serialised scheme state against `lastSavedRef.current`.
- `saveLLMConfig` from the exported return.
- The embedding-only write inside `handleLLMConfigChange` (it becomes redundant once the generic auto-save covers the whole `llm_config`).

**Add:**

- Options accepted by the hook gain `onSwapModel?: () => void` (callback to fire after a successful persist, so pipelines pick up the new config).
- A `useDebouncedAutoSave` watching the full `llmConfig` minus the mode-owned fields. Concretely, the value passed in is `stripModeFields(llmConfig)` where `stripModeFields` returns a shallow copy with `assignment_mode` and `assignment_blocks` removed. `onSave` calls `api.updateGlobalConfig({ llm_config: llmConfig })` (the full config — strip is only for change-detection). `onPersist` calls `onSwapModel?.()` and `void fetchLLMSlotsStatus()`.
- A `flushPendingSave: () => Promise<void>` return value wired to the debounced-save hook's `flush`.
- An `enabled` gate that starts false and flips to true inside `markLLMConfigClean` (called by App after the initial `getGlobalConfig`).

**Keep unchanged:**

- `handleLLMConfigChange` now just calls `setLLMConfig(cfg)` and `onDirtyRef.current?.()`. The auto-save responsibility moves to the hook.
- `handleAddEndpoint`, `handleEditEndpoint`, `handleDeleteEndpoint` — they already auto-save directly to the `saved_endpoints` slice; leave alone. Their writes interact well with the full-config debounced save because `saved_endpoints` is just another field, so the subsequent debounced save is a no-op if nothing else changed.
- `handleModeSwitch` — unchanged shape. Called by App after `flushPendingSave`.
- `markLLMConfigClean` — called by App after `getGlobalConfig` populates state.

### Refactor: `App.tsx`

File: `src/prep/dashboard/src/App.tsx`

- Remove the `saveLLMConfig` wrapper (currently at lines ~482–487) that chained `handleSwapModel` after `_rawSaveLLMConfig`. The swap now fires from inside `useDebouncedAutoSave`'s `onPersist`.
- Pass `handleSwapModel` into `useLLMConfig` via a new option (`onSwapModel`).
- Add `onModeApply` wiring passed down to `AIModelsSettings`: it calls `flushPendingSave()` first (so any in-flight slot edit is committed before the mode-restructure backend call), then awaits `handleModeSwitch(draftMode, blocks)`.

### Refactor: `AIModelsSettings.tsx`

File: `packages/ui/src/components/llm/AIModelsSettings.tsx`

**Props:**

- Drop `configDirty` and `onSave`.
- Add `onModeApply?: () => Promise<void> | void`.

**Button:**

- Only enabled when `isDraftDirty` (draft mode differs from saved mode). No more `configDirty` branch.
- `onClick={() => onModeApply?.()}`.
- Label computed from `draftMode`: `Apply ${draftMode === 'structured' ? 'Structured' : 'Assigned'} mode`.
- `handleModeSave` is removed (its contents move into `onModeApply` at the App layer).

**Always-available visibility:**

- For each of the four slot cards (Single/Fast, Thinking, Code, Coordinator), pass a new `showAlwaysOn` prop computed as `isLocalProvider(endpointProviderFor(slotEndpointId))`. `endpointProviderFor(id)` is a small local helper that looks up `config.saved_endpoints.find(e => e.id === id)?.provider`.

### New helper: `provider-utils.ts`

File: `packages/ui/src/components/llm/provider-utils.ts`

```ts
import type { LLMProvider } from '../../types'

export const LOCAL_PROVIDERS: readonly LLMProvider[] = ['ollama', 'lm-studio'] as const

export function isLocalProvider(p: LLMProvider | undefined): boolean {
  return !!p && (LOCAL_PROVIDERS as readonly string[]).includes(p)
}
```

Imported by `AIModelsSettings` and tests.

### Refactor: `ModelCard.tsx`

File: `packages/ui/src/components/llm/ModelCard.tsx`

- Add prop `showAlwaysOn?: boolean` (default `true` to preserve behaviour on cards that don't pass it).
- Update the checkbox guard:

  Before:

  ```tsx
  {onAlwaysOnChange !== undefined && (
    <label>…</label>
  )}
  ```

  After:

  ```tsx
  {showAlwaysOn && onAlwaysOnChange !== undefined && (
    <label>…</label>
  )}
  ```

Extract a tiny pure helper for testability:

```ts
export function shouldShowAlwaysOn({
  showAlwaysOn,
  onAlwaysOnChange,
}: { showAlwaysOn?: boolean; onAlwaysOnChange?: (v: boolean) => void }): boolean {
  return (showAlwaysOn ?? true) && onAlwaysOnChange !== undefined
}
```

Use `shouldShowAlwaysOn({ showAlwaysOn, onAlwaysOnChange })` at the JSX site. This keeps tests pure-logic in the same style as `buildModelOptions`.

## Data flow

```
User edits slot  →  onConfigChange  →  setLLMConfig(cfg)   [local state updates immediately]
                                                ↓
                            [1500 ms quiet window]
                                                ↓
                             useDebouncedAutoSave fires
                                                ↓
                       api.updateGlobalConfig({ llm_config })
                                                ↓
                          onPersist: handleSwapModel()      [no-op when nothing is running]
                                                ↓
                              fetchLLMSlotsStatus()          [refresh sidebar status]
```

Mode toggle path is parallel and user-triggered:

```
Click tab         →  setDraftMode(mode)   [button enables]
Click "Apply …"   →  onModeApply()
                       ↓
                  flushPendingSave()   [commit any in-flight slot edit first]
                       ↓
                  handleModeSwitch(draftMode, blocks)
                       ↓
                  switchAssignmentMode backend call (handles its own swap side-effects)
```

## Edge cases

- **Race: user toggles mode while a slot save is pending.** `onModeApply` calls `flushPendingSave()` before `handleModeSwitch`. Deterministic order; mode switch sees the latest slot config on the backend.
- **Auto-save failure.** Silent, matching the existing `saveLLMConfig` policy. Sidebar AI Gateway status indicator surfaces endpoint health separately.
- **Unmount mid-debounce.** `useDebouncedAutoSave` calls `flush()` synchronously from its cleanup. The save is fire-and-forget; unmount does not await it.
- **First render.** `enabled` starts false. App calls `markLLMConfigClean()` after `getGlobalConfig` populates state, which both sets the baseline and enables the hook. Prevents the initial hydrated state from being auto-saved back before the user touches anything.
- **Swap churn during rapid edits.** Debounce guarantees at most one `swap_model` per settled edit window. Cheap pause/resume stays cheap.
- **Endpoint change flips provider local → cloud.** `showAlwaysOn` is computed from the current endpoint's provider, so the checkbox disappears the moment the user picks a cloud endpoint. Existing persisted `always_on=true` is preserved in the config (no-op for cloud), so toggling back to a local endpoint restores the previous value.

## Testing

All tests are pure-logic vitest-style (no DOM runner currently wired in `@prep/ui`; `tsc --noEmit` compiles, and hook tests use React Testing Library + fake timers in the dashboard workspace where vitest is configured).

### `packages/ui/src/components/llm/__tests__/provider-utils.test.ts` (new)

- `isLocalProvider('ollama')` → `true`.
- `isLocalProvider('lm-studio')` → `true`.
- `isLocalProvider('openai')`, `'anthropic'`, `'google'`, `'openai-compatible'` → `false`.
- `isLocalProvider(undefined)` → `false`.

### `packages/ui/src/components/llm/__tests__/ModelCard.test.tsx` (extend existing)

- `shouldShowAlwaysOn({ showAlwaysOn: true, onAlwaysOnChange: fn })` → `true`.
- `shouldShowAlwaysOn({ showAlwaysOn: false, onAlwaysOnChange: fn })` → `false`.
- `shouldShowAlwaysOn({ onAlwaysOnChange: fn })` (no `showAlwaysOn`) → `true` (backward compat).
- `shouldShowAlwaysOn({ showAlwaysOn: true })` (no handler) → `false`.

### `src/prep/dashboard/src/hooks/__tests__/useDebouncedAutoSave.test.ts` (new)

Uses vitest fake timers.

- Does not fire before the first change.
- Fires once after `delayMs` quiet.
- Rapid successive changes coalesce into a single save with the latest value.
- `flush()` forces an immediate save and resolves after `onPersist` runs.
- Unmount with a pending save flushes synchronously (`onSave` called during cleanup).
- `enabled=false` suppresses scheduling; toggling to `true` re-baselines the current value without firing.

### `src/prep/dashboard/src/hooks/__tests__/useLLMConfig.test.ts` (new)

Uses React Testing Library + fake timers + mocked API client.

- A slot change followed by 1500 ms of quiet calls `api.updateGlobalConfig` once with the full `llm_config`, and `onSwapModel` is invoked.
- Two rapid slot changes within the window produce a single save with the latest value.
- Toggling `assignment_mode` alone (without calling `flushPendingSave`) does not trigger an auto-save (mode fields are stripped from the change-detection value).
- `flushPendingSave()` causes a pending save to run immediately.
- Initial mount + `markLLMConfigClean()` does not cause a save (no-save-on-hydrate).

## Out of scope

Explicitly not changed by this spec:

- `buildModelOptions` fix (shipped in commit `28d38d70`) — untouched.
- `getSlotStatus` `'connected'` fallback for empty `availableModels` — separate bug, separate follow-up.
- Extraction of `modelInList` / `matchesSaved` into shared helpers — deferred cleanup.
- Auto-save failure surfacing (toasts, banners). Silent policy preserved.
- Pipeline run gating when no model is configured.
- Visual redesign of the Structured / Assigned tab group.

## Acceptance

- Select a model in Single/Fast: reload after 2 s of inactivity, the selection persists. No button click.
- Select a model, then quickly change endpoint, then select a different model: only one `api.updateGlobalConfig` request fires (~1500 ms after the last change), with the final state.
- With a pipeline running, change a slot model: after 1500 ms, a `swap_model` call fires and the pipeline pauses → resumes with the new config. Rapid edits produce exactly one swap.
- Switch from Structured to Assigned mode: the "Apply Assigned mode" button enables. Clicking it calls `switchAssignmentMode`. Clicking Structured again without saving reverts the draft; the button disables.
- View the Single/Fast card with an Ollama endpoint: "Always available (Keep loaded)" checkbox is present. Switch the endpoint to an OpenAI endpoint on the same card: checkbox disappears. Switch back: checkbox reappears, previous `always_on` value preserved.
- All tests listed in the Testing section pass.
