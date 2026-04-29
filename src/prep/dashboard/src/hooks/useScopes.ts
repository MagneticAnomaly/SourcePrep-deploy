/**
 * useScopes — dashboard re-export of the shared hook from @prep/ui.
 *
 * The hook implementation and ScopesApi interface live in packages/ui so
 * they can be shared with Storybook, tests, and future consumers (VS Code
 * extension, etc.). The dashboard imports from the shared lib and re-exports
 * for local use, matching the pattern used by other shared hooks.
 */
export { useScopes } from '@prep/ui';
export type { ScopesApi } from '@prep/ui';
