# The Digital Custodian — Codebase Maintenance Agent

> **Phase 67 — Agent Concept** | Date: 2026-04-01
> This document defines the Digital Custodian — the third CoDRAG-native autonomous agent. While the Staffing Agent manages *people* and the Researcher manages *plans*, the Custodian manages the **physical state of the codebase** itself.

---

## 1. Concept: The Codebase Janitor

Every codebase accumulates cruft: dead code, orphaned test fixtures, stale TODO comments, deprecated modules that nobody dares delete because "it might break something." The Digital Custodian leverages CoDRAG's trace graph and audit engine to **prove** that code is truly dead, then cleans it up safely.

**Key differentiator from the other agents:** The Digital Custodian is the only CoDRAG agent that **writes to the codebase**. The Staffing Agent writes to Paperclip (agent definitions). The Researcher writes to Paperclip (project plans). The Custodian writes to *git* — creating branches, archiving files, and committing deletions.

**In Paperclip:** The Custodian appears as the "Maintenance Lead" employee. It authors "Cleanup Report" projects with per-file issues tracking what was deleted, what was archived, and what was flagged for human review.

---

## 2. Core Capabilities

| Capability | CoDRAG Data Source | What It Does | Example |
|-----------|-------------------|-------------|---------|
| **Dead code detection** | `codrag_audit` — unused exports, orphan modules | Identifies files and functions with zero dependents in the trace graph | `src/legacy/old_parser.py` has 0 imports anywhere |
| **Orphan file cleanup** | Trace graph — nodes with `in_degree=0` AND `out_degree=0` | Flags files that nothing imports AND that import nothing — true isolates | Test fixtures for deleted features |
| **Stale TODO removal** | TODO Scanner + `codrag_observe` staleness flags | Identifies TODO/FIXME comments that reference resolved issues or point to deleted code | `# TODO: migrate to v2 API` when v2 is already deployed |
| **Deprecated module archival** | Module clusters + drift detection + tag analysis | Moves entire modules tagged "deprecated" or "legacy" to the archive branch with full manifests | The `auth_v1/` directory after `auth_v2/` is fully deployed |
| **Consistent formatting** | Audit findings — naming conventions, style | Bulk renames for consistency, import reordering, whitespace normalization | Renaming `getUserData` to `get_user_data` across a Python module |

### 2.1 What the Custodian Does NOT Do

The Custodian is a **janitor**, not a **refactoring engine**. It does not:

- **Rewrite code** — It deletes dead code, but it doesn't rewrite live code to be better. That's the Researcher's job (to identify refactoring needs and push them as projects).
- **Fix bugs** — It removes stale TODOs, but it doesn't fix the underlying issues. Those are pushed to Paperclip as tasks.
- **Make architectural decisions** — It moves deprecated modules to the archive, but the decision to deprecate was made by a human or the Researcher.
- **Touch code in active use** — If `codrag_impact` shows even one dependent, the Custodian flags it for review instead of deleting.

---

## 3. Git Branch Strategy

The Custodian **never commits to main**. It operates on two dedicated branches:

### 3.1 Branch Architecture

```
main (protected)
  │
  ├── custodian/cleanup-2026-04-01    ← Working branch (short-lived)
  │     ├── commit: "Remove 3 orphaned test fixtures"
  │     │     └── codrag-finding: ARCH-17, ARCH-22, ARCH-23
  │     ├── commit: "Archive deprecated auth_v1 module"
  │     │     └── codrag-finding: QUAL-5
  │     └── commit: "Clean up 8 resolved TODOs"
  │           └── codrag-finding: TODO-3, TODO-7, ...
  │
  └── custodian/archive               ← Archive branch (long-lived)
        ├── archived/auth_v1/          ← Full copy of deleted module
        │     ├── __init__.py
        │     ├── auth_handler.py
        │     ├── token_manager.py
        │     └── _ARCHIVE_README.md   ← Why it was archived
        ├── archived/legacy_api/
        │     └── ...
        └── .custodian_manifest.json   ← Master index of all archived items
```

### 3.2 The Archive Branch

The `custodian/archive` branch is the Custodian's **long-term memory**. It serves as an insurance policy — if a deletion turns out to be wrong, the code is recoverable without digging through `git reflog`.

The archive branch is a simple, flat structure:
- Each archived module or file group gets its own directory under `archived/`
- Each directory includes an `_ARCHIVE_README.md` explaining why it was archived
- The root `.custodian_manifest.json` is the master index

### 3.3 The Manifest

```json
{
  "version": 1,
  "project_id": "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b",
  "entries": [
    {
      "id": "archive-001",
      "archived_at": "2026-04-01T14:30:00Z",
      "original_paths": [
        "src/legacy/auth_v1/__init__.py",
        "src/legacy/auth_v1/auth_handler.py",
        "src/legacy/auth_v1/token_manager.py"
      ],
      "archive_path": "archived/auth_v1/",
      "reason": "Module replaced by auth_v2. Zero dependents confirmed via codrag_impact.",
      "codrag_finding_id": "QUAL-5",
      "audit_state_hash": "a1b2c3d4",
      "cleanup_branch": "custodian/cleanup-2026-04-01",
      "cleanup_commit": "abc123f",
      "dependent_count_at_archive": 0,
      "restore_instructions": "git cherry-pick abc123f~1 (the commit before deletion)"
    },
    {
      "id": "archive-002",
      "archived_at": "2026-04-01T14:30:00Z",
      "original_paths": ["tests/fixtures/deprecated_auth_test.py"],
      "archive_path": "archived/deprecated_auth_test/",
      "reason": "Test fixture for archived auth_v1 module. No longer referenced.",
      "codrag_finding_id": "ARCH-17",
      "audit_state_hash": "a1b2c3d4",
      "cleanup_branch": "custodian/cleanup-2026-04-01",
      "cleanup_commit": "abc123f",
      "dependent_count_at_archive": 0,
      "restore_instructions": "git cherry-pick abc123f~1"
    }
  ]
}
```

---

## 4. The Cleanup Workflow

### 4.1 Complete Flow

```
Pipeline completes
  │
  ├── Pi Watchdog → delta scan (existing)
  ├── Researcher → topic selection + research (existing)
  │
  └── Digital Custodian wakes up
        │
        ├── Step 1: DISCOVER
        │     ├── Query codrag_audit for findings tagged:
        │     │     "dead_code", "orphan", "deprecated", "unused_export"
        │     ├── Query trace graph for nodes with 0 dependents
        │     └── Produce candidate list (max 50)
        │
        ├── Step 2: VERIFY
        │     For each candidate:
        │     ├── Run codrag_impact(file) → confirm 0 dependents
        │     ├── Check if file is in exclusion list → skip if yes
        │     ├── LLM review: "Is this truly dead, or could it be:"
        │     │     ├── Dynamically imported (importlib, __import__)
        │     │     ├── Used via reflection or eval()
        │     │     ├── Referenced in config files / env vars
        │     │     ├── A public API entry point
        │     │     └── Part of a plugin system
        │     └── Classify: SAFE_TO_DELETE | NEEDS_REVIEW | KEEP
        │
        ├── Step 3: PLAN
        │     ├── Group SAFE_TO_DELETE files by module
        │     ├── Cap at max_files_per_run (default: 20)
        │     ├── Generate archive README for each group
        │     └── Build git operation plan:
        │           ├── Branch: custodian/cleanup-{date}
        │           ├── Archive commits (copy to archive branch)
        │           └── Delete commits (remove from working branch)
        │
        ├── Step 4: EXECUTE (if not dry-run)
        │     ├── git checkout -b custodian/cleanup-{date}
        │     ├── For each group:
        │     │     ├── Copy files to custodian/archive branch
        │     │     ├── Write _ARCHIVE_README.md
        │     │     ├── Update .custodian_manifest.json
        │     │     ├── Delete files from cleanup branch
        │     │     └── Commit with message:
        │     │           "custodian: Remove {n} {module} files
        │     │            
        │     │            CoDRAG findings: ARCH-17, ARCH-22
        │     │            Archive: custodian/archive/auth_v1/
        │     │            Dependents at deletion: 0"
        │     └── (Optional) Create a pull request
        │
        └── Step 5: REPORT
              ├── Push "Cleanup Report" project to Paperclip
              │     ├── Project: "Code Cleanup: {date}"
              │     ├── Goal: Summary of what was cleaned
              │     └── Issues: One per deleted file/module
              └── Save observation via codrag_observe:
                    "Custodian archived {n} files on {date}"
```

### 4.2 Dry-Run Mode (Default)

When `dry_run: true` (the default), the Custodian executes Steps 1-3 but skips Step 4. It produces a **cleanup preview** — a list of files it *would* delete, with their dependent counts and safety classifications. This preview is:

1. Shown in the dashboard (Agent Operations → Custodian card → "Last Cleanup Preview")
2. Pushed to Paperclip as a "Cleanup Preview" project (so the team can review before enabling live mode)
3. Logged via `codrag_observe` for cross-session reference

### 4.3 Live Mode

To enable live deletions, the user must explicitly:
1. Set `dry_run: false` in the agent config
2. Confirm via CLI (`codrag custodian run --project <id>`) or dashboard button

Even in live mode, the Custodian creates a branch and (optionally) a PR. It **never pushes to main directly**.

---

## 5. Safety Guardrails

The Custodian is the highest-risk agent because it modifies code. Every design decision prioritizes safety over convenience.

| Guardrail | Why | How |
|-----------|-----|-----|
| **Never auto-merge** | Prevents accidental data loss | Custodian creates branches and PRs; a human merges |
| **Impact verification** | Prevents deleting code that's still used | Every candidate is verified via `codrag_impact` before deletion |
| **LLM safety review** | Catches dynamic imports and reflection usage | LLM reviews each candidate for non-static usage patterns |
| **Archive-first** | Provides easy recovery | Nothing is deleted without first being committed to the archive branch |
| **Dry-run default** | Prevents surprising deletions on first use | `dry_run: true` by default; must be explicitly enabled |
| **Exclusion list** | Protects important paths | Config allows paths to be excluded (docs, scripts, CI, etc.) |
| **Size cap** | Keeps PRs reviewable | Maximum files per cleanup run (default: 20) |
| **Audit trail** | Full accountability | Every deletion includes the CoDRAG finding ID, dependent count, and archive location in the commit message |
| **Manifest** | Recovery roadmap | `.custodian_manifest.json` tracks every archived item with restore instructions |

### 5.1 The Safety Verification Prompt

The LLM review is the most critical safety step. The prompt must be conservative:

```
You are reviewing a code file to determine if it is truly dead (safe to delete).

File: {file_path}
File contents (first 200 lines):
{file_contents[:200]}

CoDRAG analysis:
- Dependents (static imports): {dependent_count} (should be 0)
- This file imports: {import_list}
- Module membership: {module_name}
- Domain tags: {domain_tags}

Answer these questions:
1. Could this file be imported dynamically (importlib, __import__, exec)?
2. Could this file be referenced via string-based paths (config files, env vars)?
3. Is this file a public API entry point (exposed via __init__.py, __all__)?
4. Is this file part of a plugin system or extension mechanism?
5. Could this file be a CLI entry point, test fixture, or script?
6. Is there any reason a human might want to keep this file?

If ANY answer is "yes" or "uncertain", classify as NEEDS_REVIEW.
If ALL answers are "no", classify as SAFE_TO_DELETE.
Never default to SAFE_TO_DELETE if uncertain.

Return JSON: {"classification": "SAFE_TO_DELETE" | "NEEDS_REVIEW" | "KEEP", "reason": "..."}
```

---

## 6. Configuration

```json
{
  "agents": {
    "custodian": {
      "enabled": false,
      "adapter": "native",
      "dry_run": true,
      "max_files_per_run": 20,
      "archive_branch": "custodian/archive",
      "auto_pr": false,
      "exclude_paths": [
        "docs/",
        "scripts/",
        ".github/",
        ".agents/",
        "*.md",
        "LICENSE",
        "README*"
      ],
      "min_finding_confidence": 0.7,
      "cooldown_seconds": 86400,
      "trigger": "manual"
    }
  }
}
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Master switch. Must be explicitly enabled. |
| `adapter` | string | `"native"` | `"native"`, `"langgraph"`, or `"crewai"` |
| `dry_run` | bool | `true` | If true, discover and plan but don't execute git operations |
| `max_files_per_run` | int | `20` | Maximum files to process per cleanup cycle |
| `archive_branch` | string | `"custodian/archive"` | Name of the long-lived archive branch |
| `auto_pr` | bool | `false` | If true, automatically create a PR after cleanup |
| `exclude_paths` | list | `[docs/, scripts/, ...]` | Glob patterns to exclude from custodian's scope |
| `min_finding_confidence` | float | `0.7` | Minimum audit confidence score to consider a finding |
| `cooldown_seconds` | int | `86400` (24h) | Minimum time between cleanup runs |
| `trigger` | string | `"manual"` | `"manual"` (CLI/dashboard only) or `"post-pipeline"` (auto-run after rebuild) |

---

## 7. CLI Commands

```bash
# Run a cleanup cycle (respects dry_run config)
codrag custodian run --project <id>

# Force dry-run regardless of config
codrag custodian run --project <id> --dry-run

# Force live mode (overrides config, still creates branch)
codrag custodian run --project <id> --live

# Use a specific adapter
codrag custodian run --project <id> --adapter langgraph

# View the archive manifest
codrag custodian archive --project <id>

# Restore a specific file from archive
codrag custodian restore --project <id> --file src/legacy/old_parser.py

# Restore by archive entry ID
codrag custodian restore --project <id> --entry archive-001
```

---

## 8. Dashboard Integration

The Digital Custodian card in the Agent Operations panel shows:

**Level 1 (Compact Card):**
```
┌───────────────┐
│ 🧹 Custodian  │
│  Agent        │
│               │
│ 12 candidates │
│ Last: 2d ago  │
│ ⚪ Dry Run    │
└───────────────┘
```

**Level 2 (Detail Section in System Agents tab):**
```
┌─── 🧹 Digital Custodian ─────────────────────────────────┐
│                                                           │
│  Status: ⚪ Dry Run        Adapter: Native                │
│  Last Run: 2d ago         Candidates: 12                  │
│  Branch: custodian/archive  Max Files: 20                 │
│  Archive Size: 47 files     Auto PR: Off                  │
│                                                           │
│  Model: qwen3:8b ← Configure in AI Gateway               │
│                                                           │
│  [Run Cleanup] [View Archive] [Configure]                 │
│                                                           │
│  ── Last Cleanup Preview ──                               │
│  🗑️ test-fixtures/deprecated_auth.py (0 deps) SAFE       │
│  🗑️ src/legacy/old_parser.py (0 deps) SAFE               │
│  ⚠️ src/utils/helpers.py (1 dep) NEEDS_REVIEW            │
│  ✅ src/core/engine.py (14 deps) KEEP                     │
│                                                           │
│  ── Archive History ──                                    │
│  • 2d ago: Archived 5 files (auth_v1 module)             │
│  • 1w ago: Archived 3 test fixtures                      │
│  • 2w ago: First run — 12 candidates, 8 archived         │
└───────────────────────────────────────────────────────────┘
```

---

## 9. Paperclip Integration

When the Custodian completes a cleanup run, it pushes a "Cleanup Report" project to Paperclip:

```json
{
  "project": {
    "name": "Code Cleanup: 2026-04-01",
    "description": "Digital Custodian cleanup report. 8 files archived, 4 flagged for review.",
    "source": "custodian_agent",
    "priority": "P3"
  },
  "goals": [
    {
      "title": "Archive deprecated auth_v1 module",
      "description": "3 files moved to custodian/archive. Zero dependents confirmed.",
      "priority": "P3",
      "status": "completed"
    }
  ],
  "issues": [
    {
      "title": "Review: src/utils/helpers.py has 1 dependent",
      "description": "Custodian flagged this file but it has 1 remaining dependent: src/core/engine.py. Manual review needed to determine if the dependency can be removed.",
      "priority": "P3",
      "status": "pending"
    }
  ]
}
```

This creates a visible audit trail in Paperclip. The team can review the Custodian's work, approve or reject individual decisions, and track cleanup progress over time.

---

## 10. Future Enhancements (Not in Initial Build)

| Enhancement | Description | Blocked On |
|-------------|-------------|-----------|
| **Auto-merge confidence threshold** | If the Custodian's classification confidence is > 0.95 for ALL files in a PR, auto-merge | Trust + real-world validation |
| **Import graph visualization** | Dashboard shows a visual graph of what the Custodian is about to delete and why | Graph rendering in dashboard |
| **Cross-project archival** | Archive code from one CoDRAG project into another's archive branch | Multi-project support |
| **Scheduled runs** | Cron-like scheduling for the Custodian (e.g., weekly cleanup) | Agent scheduler infrastructure |
| **Undo button** | One-click restore from the dashboard | Git integration in dashboard |
