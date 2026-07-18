/**
 * Centralized beta-mode toggle for the marketing site — single source of truth.
 *
 * All pages import `IS_BETA_MODE` from here instead of declaring a per-page
 * `const IS_BETA_MODE = true`. The old per-page constant was a dev-only switch
 * duplicated across 6 files: flipping beta → final meant editing 6 files and
 * risked the pages drifting out of sync. This module makes the flip a one-place
 * change.
 *
 * Value is build-time (NEXT_PUBLIC_ vars are inlined by Next.js at build):
 *   - unset / "true"  → beta mode ON  (ship the "in beta" version)
 *   - "false"         → beta mode OFF (post-beta, go live with final copy)
 *
 * Default is ON so the beta ship can't be accidentally silenced by a missing
 * env var. The post-beta deploy MUST set NEXT_PUBLIC_BETA_MODE=false explicitly
 * — do not go live with beta mode still on.
 */
export const IS_BETA_MODE: boolean =
  (process.env.NEXT_PUBLIC_BETA_MODE ?? "true").toLowerCase() !== "false";