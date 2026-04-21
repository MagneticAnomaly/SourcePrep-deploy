# UI API Integration (Draft)

This folder defines a **typed, Storybook-friendly** API client for the Prep daemon.

## Design goals

- **Typed endpoints** that mirror `docs/API.md`.
- **Stable envelope parsing** (`{ success, data, error }`).
- **Mockable by default** in Storybook (no MSW requirement).
- **Auth-ready** for team/network mode via optional Bearer token.

## Usage

Create a client:

- `createPrepApiClient({ baseUrl, apiKey })`

Call endpoints:

- `client.listProjects()`
- `client.getProjectStatus(projectId)`
- `client.search(projectId, { query, k, min_score })`
- `client.assembleContext(projectId, { query, max_chars, structured, trace_expand })`

Errors:

- Methods throw `ApiClientError` when the HTTP request fails or the API envelope reports `success=false`.

## Storybook mocking

Prefer injecting a mock client rather than intercepting network.

- Use `createMockApiClient({ ...overrides })` to define only the methods needed for a story.
- Wrap stories with `ApiClientProvider` so child components/hooks can access the client.

This keeps stories deterministic and avoids adding MSW until we need real request-level behavior.
