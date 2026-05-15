"use client";

// Thin client-component boundary so docs pages can stay server components
// while still embedding @prep/ui's animation components and named scripts.
// @prep/ui uses React.createContext (client-only), so importing it directly
// from a server-rendered page.tsx breaks the Next build.

export {
  AnimatedCLI,
  AnimatedIDE,
  // Sequence arrays
  prepDemos,
  prepSearchDemos,
  prepImpactDemos,
  prepAuditDemos,
  prepObserveDemos,
  prepConceptsDemos,
  ideDemos,
  // Single-script aliases (first pick of each sequence)
  prepOverviewDemo,
  prepSearchDemo,
  prepImpactDemo,
  prepAuditDemo,
  prepObserveDemo,
  prepConceptsDemo,
  ideDemoScript,
  // Named individual scripts
  prepRateLimitingDemo,
  prepTldrOverviewDemo,
  prepBuildWebhookDemo,
  searchRetryReuseDemo,
  searchMaxConnectionsDemo,
  searchBuildWorkerDemo,
  impactDeleteUnusedDemo,
  impactExtractServiceDemo,
  impactAsyncMigrationDemo,
  auditPrSanityCheckDemo,
  auditSecurityScanDemo,
  auditTightenTypesDemo,
  observeCachingRecallDemo,
  observeInvestigationRecallDemo,
  observeSaveOwnershipDemo,
  conceptsTransactionRuleDemo,
  conceptsQueuePitfallsDemo,
  conceptsBuildRefundDemo,
  ideDoubleSubmitFixDemo,
  ideLoadingSkeletonDemo,
  ideAddCsvExportDemo,
} from '@prep/ui';
