# Phase 27: Bug Reporting System

## Overview

One-click bug reporting from the CoDRAG dashboard. Users click the bug icon in the
Process Logs panel, fill out a short form (email + description), and the app
auto-collects **comprehensive** diagnostics and submits everything to our ingestion
service. Offline fallback: download the report as a JSON file and email it.

**Design principle:** build for MVP now (email-as-storage), but schema and
architecture are forward-compatible with a full ticket system.

---

## Architecture

```
┌──────────────────────┐        ┌─────────────────────────────┐
│  CoDRAG Dashboard    │  POST  │  support.codrag.io          │
│  (Tauri / Browser)   │───────>│  /api/bug-report            │
│                      │        │  (Next.js API route, Vercel)│
│  BugReportModal      │        └──────┬──────────────────────┘
│  ├─ email            │               │
│  ├─ description      │               ├─ validate + rate limit
│  ├─ severity         │               ├─ generate report ID
│  ├─ steps            │               ├─ log to Vercel logs
│  └─ auto-diagnostics │               │
│     (27 data points) │               ▼
└──────────────────────┘        ┌──────────────────┐
                                │  Resend           │
        Offline fallback:       │  ├─ HTML summary  │
        Download JSON +         │  ├─ JSON attached │
        email manually          │  └─ reply-to user │
                                └──────┬───────────┘
                                       │
                                       ▼
                                ┌──────────────────┐
                                │  bugs@codrag.io   │
                                │  inbox            │
                                └──────────────────┘
```

### MVP: Next.js API route in support app

The `@codrag/support` app (deployed to `support.codrag.io` on Vercel) already
exists. The bug report endpoint is a serverless API route at
`/api/bug-report`. This avoids spinning up new infrastructure.

- **Validation**: email, description (min 10 chars), severity enum
- **Rate limiting**: 10 reports/hour per IP (in-memory, per-process)
- **Notification**: Resend email with HTML summary + full JSON attachment
- **CORS**: `Access-Control-Allow-Origin: *` (no secrets in payload)
- **Logging**: every report logged to Vercel function logs as backup

### Sending directly from the app

**Yes — the Tauri app has no CORS restrictions.** The frontend POSTs directly.
For the browser dashboard, CORS headers are set on the API route.

### Offline fallback

If the endpoint is unreachable (offline, timeout, error), the modal
auto-downloads the report as `codrag-bug-report-{date}.json` and shows
instructions to email it to `support@codrag.io`.

---

## Diagnostic Data Collected (27 data points)

Every bug report automatically includes ALL of the following. The user can
preview this in the modal before sending.

### Platform (auto-detected)
| Field | Source |
|-------|--------|
| `user_agent` | `navigator.userAgent` |
| `os` | `navigator.platform` |
| `screen` | `screen.width x screen.height` |
| `language` | `navigator.language` |
| `online` | `navigator.onLine` |
| `tauri` | `window.__TAURI__` presence |

### Session Logs
- **All captured logs** — timestamp, level, logger, message
- Unfiltered (even if user has a filter active in the console)

### Project State
| Field | Description |
|-------|-------------|
| `project` | id, name, path, mode |
| `project_status` | building, stale, stale_since, stale_count, full index stats, full trace stats, watch status |
| `project_config` | include/exclude globs, max_file_bytes, use_gitignore, trace config, auto_rebuild config |

### Systems State
| Field | Description |
|-------|-------------|
| `license_tier` | free or pro+ |
| `trace_status` | full trace system status (from useTraceSystem) |
| `trace_coverage` | coverage statistics |
| `watch_status` | watcher state + loading flag |
| `scope_status` | scope events for current project |
| `index_auto_rebuild` | boolean |
| `enrichment_auto_config` | auto enrichment settings |

### Enrichment Pipeline State
| Field | Description |
|-------|-------------|
| `augmentation` | status object + `augmenting` flag + `validating` flag |
| `epistemic` | status object + `running` flag |
| `modules` | status object + `cluster_running` flag |
| `deepening` | status object + `running` flag |
| `knowledge` | status object + `building` flag |

### LLM Configuration
| Field | Description |
|-------|-------------|
| `embedding` | full embedding config |
| `small_model` | endpoint_id + model (no API keys) |
| `large_model` | endpoint_id + model (no API keys) |
| `clara` | full CLaRa config |
| `saved_endpoints` | id, name, provider, url (no API keys) |
| `llm_slots_status` | which models are loaded/ready |

### Task & Schedule State
| Field | Description |
|-------|-------------|
| `active_tasks` | current index_build and trace_build tasks with progress |
| `deep_analysis_schedule` | current deep analysis settings |
| `transient_complete` | whether a build just completed |

**Security note:** API keys are deliberately excluded from `saved_endpoints`.
Only endpoint URLs and provider names are included.

---

## Report Payload Schema

```jsonc
{
  "report_version": "1",
  "generated_at": "2026-02-18T20:56:00.000Z",

  // User-provided fields
  "reporter": { "email": "user@example.com" },
  "issue": {
    "severity": "major",           // critical | major | minor | cosmetic
    "description": "Detailed description of what happened...",
    "steps_to_reproduce": "1. Opened project\n2. Clicked build\n3. ...",
    "expected_behavior": "Build should complete",
    "actual_behavior": "Build hung at 50%"
  },

  // Auto-collected — see "Diagnostic Data Collected" above
  "platform": { ... },
  "diagnostics": { ... },
  "logs": [
    { "time": "2026-02-18T20:55:30.000Z", "level": "ERROR", "logger": "codrag.core.index", "message": "..." }
  ]
}
```

---

## Frontend Implementation

### Components

| Component | Location | Status |
|-----------|----------|--------|
| `BugReportModal` | `packages/ui/src/components/console/BugReportModal.tsx` | ✅ Done |
| `LogConsole` (updated) | `packages/ui/src/components/console/LogConsole.tsx` | ✅ Done |
| `diagnosticData` wiring | `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` | ✅ Done |

### BugReportModal UX

1. **Bug icon click** → modal opens (portal to document.body)
2. **Form fields:**
   - Email (required) — remembered in localStorage for convenience
   - Severity selector: Critical / Major / Minor / Cosmetic (default: Major)
   - Description textarea (required, 4+ rows, placeholder encourages verbosity)
   - Steps to Reproduce textarea (optional but encouraged, placeholder with numbered list)
   - Expected vs Actual behavior (optional, collapsible)
3. **Auto-diagnostics section** — collapsible "What we'll include" showing a
   summary of collected data (platform, project status, logs count, etc.).
   User can review before sending.
4. **Submit button** — "Send Report"
   - Tries POST to `support.codrag.io/api/bug-report` (10s timeout)
   - On success: green confirmation, modal auto-closes after 3s
   - On failure: auto-downloads JSON + amber warning with email fallback
5. **Download button** — always available for manual download
6. **Escape key** closes modal

### Props flow

```
App.tsx
  └─ useDashboardPanels (assembles diagnosticData from ALL system hooks)
       └─ LogConsole (bug icon onClick → setBugReportOpen(true))
            └─ BugReportModal (open, onClose, logs, diagnosticData)
```

---

## Cloud Ingestion Service

### MVP: Next.js API route (DONE)

**Location:** `websites/apps/support/src/app/api/bug-report/route.ts`

#### Endpoint

```
POST https://support.codrag.io/api/bug-report
Content-Type: application/json
```

#### Logic

1. Rate limit check (10/hr per IP)
2. Validate payload (email, description min 10 chars, severity enum)
3. Generate report ID: `br-{base36-timestamp}-{random}`
4. Log to Vercel function logs (always available as backup)
5. Send notification via Resend:
   - To: `bugs@codrag.io` (configurable via `BUG_REPORT_EMAIL` env var)
   - Reply-To: reporter's email
   - Subject: `{severity emoji} [Bug SEVERITY] first 80 chars of description`
   - Body: HTML summary table + description + steps + recent errors (last 20)
   - Attachment: full report JSON
   - Tags: category, severity, report_id (for Resend analytics)
6. Return `{ success: true, report_id, email_sent, message }`

#### Response codes

| Code | Meaning |
|------|---------|
| 200  | Report accepted |
| 400  | Validation error (missing email/description) |
| 429  | Rate limit (max 10 reports/hour per IP) |

#### Environment variables

| Var | Required | Default |
|-----|----------|---------|
| `RESEND_API_KEY` | For email | None (logs only if missing) |
| `BUG_REPORT_EMAIL` | No | `bugs@codrag.io` |

#### CORS

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Ticket System Roadmap (Future)

The MVP uses email-as-storage. The schema and IDs are designed to migrate
to a proper ticket system without breaking anything.

### Phase 27.2 — Persistent Storage

| ID | Task | Est |
|----|------|-----|
| BR-8 | Add Vercel Postgres (or D1/Supabase) `reports` table | 1h |
| BR-9 | Insert report metadata on receipt (id, status, severity, email, created_at) | 30m |
| BR-10 | Store full JSON in Vercel Blob / R2 | 30m |
| BR-11 | API: `GET /api/bug-reports` (list, paginated, auth-gated) | 30m |
| BR-12 | API: `GET /api/bug-report/:id` (detail, auth-gated) | 15m |
| BR-13 | API: `PATCH /api/bug-report/:id` (update status, assign) | 15m |

### Phase 27.3 — Admin Dashboard

| ID | Task | Est |
|----|------|-----|
| BR-14 | Admin page at `support.codrag.io/admin/reports` (auth-gated) | 2h |
| BR-15 | List/detail views for reports | 2h |
| BR-16 | Status tracking: New → Triaging → Investigating → Fixed → Closed | 1h |
| BR-17 | Search + severity/status filters | 1h |
| BR-18 | Metrics: reports per day, severity distribution, common loggers | 1h |

### Planned `reports` Table Schema

```sql
CREATE TABLE reports (
  id          TEXT PRIMARY KEY,           -- br-{ts}-{rand}
  status      TEXT DEFAULT 'new',         -- new | triaging | investigating | fixed | closed
  severity    TEXT NOT NULL,              -- critical | major | minor | cosmetic
  email       TEXT NOT NULL,
  description TEXT NOT NULL,
  project_id  TEXT,
  license_tier TEXT,
  platform    TEXT,                       -- OS string
  log_count   INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0,
  blob_key    TEXT,                       -- reference to full JSON in blob storage
  assigned_to TEXT,
  resolution  TEXT,
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_severity ON reports(severity);
CREATE INDEX idx_reports_created ON reports(created_at DESC);
```

---

## Configuration

```typescript
// Frontend (BugReportModal.tsx)
const BUG_REPORT_ENDPOINT = 'https://support.codrag.io/api/bug-report';
const SUBMIT_TIMEOUT_MS = 10_000;
```

```bash
# Backend (support app .env.local)
RESEND_API_KEY=re_...
BUG_REPORT_EMAIL=bugs@codrag.io
```
