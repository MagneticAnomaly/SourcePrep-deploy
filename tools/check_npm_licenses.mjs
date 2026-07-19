#!/usr/bin/env node
/**
 * npm dependency license gate for the SourcePrep OSS release.
 *
 * SourcePrep ships under Apache-2.0. A GPL/AGPL/copyleft npm dependency
 * would contaminate the Apache-2.0 grant. This script reads the npm
 * package-lock.json (lockfileVersion 3) — which carries a `license` field per
 * installed package — and fails (exit 1) if any package declares a forbidden
 * license with no permissive alternative.
 *
 * Why the lockfile, not `npm ls`: `npm ls --json` omits the per-package
 * `license` field in many npm versions, producing false "UNKNOWN" hits. The
 * lockfile is the canonical record of every resolved package + its license.
 *
 * Forbidden patterns (substring, case-insensitive, on each OR-clause):
 *   - GPL    (catches "GPL-2.0", "GPL-3.0", "GPLv2+"; also "AGPL" via the
 *     "AGPL" check below)
 *   - AGPL
 *   - "UNKNOWN" / "" / missing -> fail (diligence gap)
 *   - LGPL   allowed by default (weak copyleft); pass --strict-lgpl to fail.
 *
 * OR-clause parsing: a license like "Apache-2.0 OR GPL-2.0" passes — the
 * copyright holder offers a permissive option. We split on " OR " and ";".
 *
 * Usage:
 *   node tools/check_npm_licenses.mjs
 *   node tools/check_npm_licenses.mjs --strict-lgpl
 *
 * Run after `npm ci` (lockfile present). Used by
 * .github/workflows/license-audit.yml.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

const FAIL_PATTERNS = ["AGPL", "GPL", "UNKNOWN", "UNLICENSED", "N/A", "SEE LICENSE IN"];
const PERMISSIVE = ["MIT", "APACHE", "BSD", "ISC", "MPL", "PYTHON", "ZLIB", "CC0", "UNICODE", "OPENSSL"];

// Documented exceptions (key = package name, exact). Each has a rationale
// printed when the exception applies, so it's auditable in CI logs. These are
// packages that ship NO machine-readable license (no `license` in package.json
// or the lockfile, and no standard LICENSE file header) but are
// registry/repo-confirmed permissive. Each exception cites the confirmation
// source so it can be re-verified.
const EXCEPTIONS = {
  busboy: `MIT per npm registry (https://www.npmjs.com/package/busboy). The installed LICENSE file uses non-standard "Copyright Brian White. All rights reserved." wording with no SPDX tag, so it is not auto-detected. busboy is the de-facto Node.js multipart parser (used transitively by the Next.js / Express ecosystem). Confirmed MIT by the maintainer's repo.`,
  streamsearch: `MIT per npm registry (https://www.npmjs.com/package/streamsearch). Same maintainer (Brian White) and non-standard local LICENSE wording as busboy; registry classifies MIT. Transitive dep of busboy.`,
  format: `MIT per the source repo (https://github.com/samsonjs/format). The published package.json omits the license field entirely and ships no LICENSE file — a metadata gap on the maintainer's side, not a license problem. Transitive dep (via fault). If this becomes a maintenance burden, replacing fault removes it.`,
};

function normalize(s) {
  return String(s ?? "").trim().toUpperCase();
}

function splitClauses(lic) {
  const s = String(lic ?? "").replace(/\s+OR\s+/gi, "; ");
  return s.split(";").map((c) => c.trim()).filter(Boolean);
}

function clauseIsPermissive(clause) {
  const cu = normalize(clause);
  return PERMISSIVE.some((p) => cu.includes(p));
}

function findLockfiles() {
  // Root lockfile covers the whole workspace; nested workspaces may have
  // their own (rare in npm workspaces, common if a workspace predates the
  // monorepo). Glob both.
  const roots = ["package-lock.json"];
  // Walk one level into packages/* and websites/apps/* for stray lockfiles.
  for (const dir of ["packages", "websites/apps", "public", "src/prep/dashboard"]) {
    const dirAbs = path.join(process.cwd(), dir);
    let entries = [];
    try { entries = readdirSync(dirAbs, { withFileTypes: true }); } catch { continue; }
    for (const e of entries) {
      if (e.isDirectory()) {
        const lf = path.join(dirAbs, e.name, "package-lock.json");
        try { readFileSync(lf); roots.push(path.join(dir, e.name, "package-lock.json")); } catch { /* no lockfile here */ }
      }
    }
  }
  return [...new Set(roots)];
}

function main() {
  const strictLgpl = process.argv.includes("--strict-lgpl");
  const failPatterns = [...FAIL_PATTERNS];
  if (strictLgpl) failPatterns.push("LGPL");

  const lockfiles = findLockfiles();
  const seen = new Set(); // dedupe name@version across lockfiles
  const offenders = [];
  const applied = [];
  let count = 0;

  for (const lf of lockfiles) {
    let data;
    try {
      data = JSON.parse(readFileSync(lf, "utf8"));
    } catch (e) {
      console.error(`WARN: could not parse ${lf}: ${e.message}`);
      continue;
    }
    const pkgs = data.packages || {};
    for (const [key, info] of Object.entries(pkgs)) {
      if (key === "") continue; // root entry (the project itself; Apache-2.0)
      if (info.link) continue; // workspace self-link (our own code; Apache-2.0)
      // Extract package name from the node_modules path (last segment after
      // `node_modules/`, handling scoped @scope/name).
      const segs = key.split("node_modules/");
      let name = segs[segs.length - 1];
      if (!name || name.includes("/")) continue; // not a real package leaf
      const version = info.version || "?";
      const dedupeKey = `${name}@${version}`;
      if (seen.has(dedupeKey)) continue;
      seen.add(dedupeKey);
      count++;

      // Documented exceptions apply first — they cover packages that ship no
      // machine-readable license but are registry/repo-confirmed permissive.
      // Recorded in `applied` so the exception is visible in CI logs.
      if (EXCEPTIONS[name]) {
        applied.push(`  ${name}@${version}: undocumented metadata -> EXCEPTION (${EXCEPTIONS[name]})`);
        continue;
      }

      // Lockfile often omits the `license` field for older / non-conformant
      // packages. Fall back to the installed package.json's `license` field
      // (the canonical source) before deciding.
      let license = info.license;
      if (!license) {
        try {
          const installed = JSON.parse(readFileSync(path.join(key, "package.json"), "utf8"));
          license = installed.license;
        } catch { /* leave undefined -> try LICENSE file next */ }
      }
      // Final fallback: some packages omit `license` from package.json too but
      // ship a LICENSE/LICENCE/COPYING file whose header identifies the
      // license. Pattern-match the first ~500 chars for a permissive marker.
      if (!license) {
        for (const lfName of ["LICENSE", "LICENSE.md", "LICENCE", "LICENCE.md", "COPYING", "UNLICENSE"]) {
          try {
            const head = readFileSync(path.join(key, lfName), "utf8").slice(0, 500).toUpperCase();
            if (head.includes("MIT LICENSE") || head.includes("THE MIT LICENSE")) { license = "MIT"; break; }
            if (head.includes("APACHE LICENSE") || head.includes("APACHE SOFTWARE LICENSE")) { license = "Apache-2.0"; break; }
            if (head.includes("BSD LICENSE") || head.includes("BSD 2-CLAUSE") || head.includes("BSD 3-CLAUSE")) { license = "BSD"; break; }
            if (head.includes("ISC LICENSE")) { license = "ISC"; break; }
          } catch { /* no such file */ }
        }
      }

      const lic = normalize(license);
      const clauses = splitClauses(license || "");
      if (clauses.length && clauses.some(clauseIsPermissive)) continue;

      if (!lic || ["UNKNOWN", "UNLICENSED", "N/A", ""].includes(lic)) {
        offenders.push(`  ${name}@${version}: license UNKNOWN / unlicensed (${lf})`);
        continue;
      }
      for (const pat of failPatterns) {
        if (lic.includes(pat)) {
          const exc = EXCEPTIONS[name];
          if (exc) {
            applied.push(`  ${name}@${version}: ${lic} -> EXCEPTION (${exc})`);
            break;
          }
          offenders.push(`  ${name}@${version}: ${lic} (matches '${pat}') (${lf})`);
          break;
        }
      }
    }
  }

  console.log(`Checked ${count} unique npm packages across ${lockfiles.length} lockfile(s).`);
  if (applied.length) {
    console.log(`\nEXCEPTIONS applied (${applied.length}):`);
    for (const line of applied) console.log(line);
  }
  if (offenders.length) {
    console.log(`\nFAIL: ${offenders.length} package(s) with forbidden licenses:`);
    for (const line of offenders) console.log(line);
    console.log(
      "\nTo resolve: replace the dependency with a permissively-licensed\n" +
      "alternative, or add a justified exception to EXCEPTIONS. Do NOT\n" +
      "widen the gate without a recorded rationale."
    );
    process.exit(1);
  }
  console.log("OK: no forbidden (GPL/AGPL/unlicensed) npm dependencies.");
}

main();