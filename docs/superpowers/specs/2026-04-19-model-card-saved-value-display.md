# ModelCard: display saved model value when endpoint list hasn't loaded

## Problem

On the AI Models settings panel (`AIModelsSettings`), model dropdowns for Single/Fast, Code, and Thinking slots show the placeholder "Select a model..." even though a model is persisted in the backend config and the pipeline runs with it correctly.

This is a UI-only regression. The config is intact; only the display is wrong. Users cannot tell at a glance which model is configured, and saving from this state would clobber the persisted selection with an empty string.

## Root cause

`packages/ui/src/components/llm/ModelCard.tsx` (around lines 198–213) builds the Model `<Select>`'s options exclusively from the `availableModels` prop:

```ts
options={[
  { value: '', label: loadingModels ? 'Loading models...' : 'Select a model...' },
  ...availableModels.map(m => ({ value: m, label: m })),
]}
```

The saved `model` prop supplies the select's `value`. When `availableModels[endpoint_id]` is empty — which happens whenever the endpoint hasn't been probed yet, the probe failed silently (cold Ollama, unreachable cloud endpoint, network blip), or the probe is still in flight on first paint — the native `<select>` cannot find an option whose `value` matches `model`. HTML falls back to the first option, which is the empty-string placeholder. The select visually reads "Select a model..." while `config.*.model` still holds the real value.

`handleFetchModels` in `useLLMConfig.ts` returns `[]` on any fetch failure and sets `availableModels[endpointId] = []`, so once a probe fails the empty list sticks until the user clicks Refresh or restarts.

Separately, `getSlotStatus` in `AIModelsSettings.tsx:688–701` returns `'connected'` when `availableModels[endpoint_id]` is empty and no fetch is in flight. That's why the screenshot shows green "Connected" badges next to empty dropdowns — the two code paths disagree about what "no list" means.

## Fix

Make the Model `<Select>` include the currently-saved `model` as an option whenever it is not already present in `availableModels`. The saved value becomes selectable and the dropdown accurately reflects the persisted config. Behavior is unchanged when `availableModels` is populated and contains the saved model.

### Change site

Single file: `packages/ui/src/components/llm/ModelCard.tsx`, inside the Model selector block (currently around lines 198–213).

### Logic

```ts
const matchesSaved = (m: string): boolean =>
  m === model ||
  m === `${model}:latest` ||
  model === `${m}:latest` ||
  m.replace(/:latest$/, '') === (model ?? '').replace(/:latest$/, '');

const savedNotInList = !!model && !availableModels.some(matchesSaved);

const options = [
  ...(model
    ? []
    : [{ value: '', label: loadingModels ? 'Loading models...' : 'Select a model...' }]),
  ...(savedNotInList ? [{ value: model!, label: model! }] : []),
  ...availableModels.map(m => {
    const details = modelDetails?.find(d => d.name === m);
    const isBlocked = (details as any)?.blocked_by_policy;
    return {
      value: m,
      label: isBlocked ? `🚫 ${m} (Blocked by IT)` : m,
      disabled: isBlocked,
    };
  }),
];
```

The `matchesSaved` predicate reuses the same `:latest` normalization already used elsewhere in `AIModelsSettings.tsx` (`modelInList`). If a small shared helper already exists, import it; otherwise inline here and leave extraction for a later cleanup.

When the user subsequently refreshes the endpoint list, the normal `availableModels` entries appear and the synthetic entry is no longer needed — `savedNotInList` becomes false and the extra option disappears.

### Placeholder behavior

The `{ value: '', label: 'Select a model...' }` placeholder is only included when `model` is unset. Previously it was always first, which was harmless when a matching option existed (browser skipped it) but active when none did. Keeping it out of the list when a value is already saved removes any chance of the native select preferring it.

## Testing

One test in `packages/ui/src/components/llm/__tests__/` (create the folder if needed, following the existing `__tests__` convention elsewhere in `packages/ui`):

- Render `ModelCard` with `model="qwen3:8b"`, `endpoint="default_ollama"`, `endpoints=[{ id: 'default_ollama', ... }]`, and `availableModels={[]}`.
- Assert the Model select element's `value` is `"qwen3:8b"` (not `""`).
- Assert the visible option text for that value is `"qwen3:8b"`.
- Second case: same setup but `availableModels=["qwen3:8b", "gemma3:12b"]`. Assert `value` is still `"qwen3:8b"` and there is exactly one option for it (no duplicate synthetic entry).
- Third case: `model=""` and `availableModels=[]`. Assert `value` is `""` and the placeholder "Select a model..." is present.

No backend, API, or persistence changes required.

## Out of scope

- Pipeline run gating when no models are configured. The backend refuses to run without a model anyway; revisit only if the accurate-display fix reveals a real hole.
- Auto-save of model selections (currently requires "Set model scheme" click). The explicit-save flow is unchanged.
- `getSlotStatus` cleanup in `AIModelsSettings.tsx`. The "empty list → connected" fallback is separate noise; leave it for a follow-up unless the display fix exposes it as a problem.
- Refactoring `modelInList` / `findRecommended` / the new `matchesSaved` predicate into a shared helper. Follow-up cleanup.

## Acceptance

- Reload the dashboard with a saved-but-unreachable endpoint (e.g., Ollama stopped). The Model dropdown shows the saved model, not "Select a model...".
- Reload with a reachable endpoint. Behavior is visually identical to today once the endpoint probe returns.
- Test file above passes.
