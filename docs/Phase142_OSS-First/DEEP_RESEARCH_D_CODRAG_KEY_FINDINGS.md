# Deep-Research D — `codrag.key` history scan + rotation plan (DR-6 + ED-6 prefix)

> Findings for the 2026-07-19 legal+security+message audit follow-up (Session D).
> Full audit: `docs/Phase142_OSS-First/LEGAL_SECURITY_MESSAGE_AUDIT_2026-07-19.md`.
> **Read-only session.** No key generated, no key rotated, no history rewritten,
> no force-push, no `.github/workflows/` modified. Everything below is a scan
> result or a *proposed* plan for Eric to approve — not an applied change.
> Method: native `git` (log/rev-list/cat-file/ls-tree/find-object) + `grep` +
> `python3` (blob-content sweep). One 4-agent adversarial-verification workflow
> (`wf_d69b2df2-700`) cross-checked the gate reading, CI-wiring, and Tauri
> rotation; its 4th agent (an independent secret re-sweep) was stopped after it
> stalled re-running the full-history diff — this doc's §1 rests on the lead
> session's own more-granular blob-level enumeration, which is stronger.

---

## TL;DR

1. **`codrag.key` is the ONLY real secret / private-key *file* in the entire git
   history.** Verified three independent ways (filename scan, blob `--find-object`,
   and a content sweep of every history blob). Every other "secret marker" hit
   maps to a **test fixture, a docs example, a format quote, a detection regex, or
   the gate's own output manifest** — zero operational secrets. The committed
   settings DB (186 fat historical versions) and 14 trace logs contain **no real
   credentials** either.
2. **The public-mirror gate works but is MANUAL, not CI-wired.** It fails closed
   and never copies history (fresh-initial-commit), so origin history is
   structurally never published *by the mirror*. But nothing mechanically forces
   the gate before a publish, and **two manual subtree-publish scripts bypass it
   entirely with full history**.
3. **`codrag.key` = Tauri v1 *updater* signing key** (`tauri.conf.json:66` /
   `codrag.key.pub`, key-id `C43F6BF18AEA1FE0`). It is **NOT** the license key
   (`licensing.py:22`, separate, Phase 146). **No signed release was ever shipped**
   → rotation is **trivial** (no stranded installs, deprecation window moot).
4. **New in-scope finding:** `src/codrag_data/codrag_settings.db` (0-byte) +
   `ui_config.json` are on origin/main, **not path-denied, and were INCLUDED in the
   last mirror manifest** — the dead-codename path would ship in the public mirror.
5. **ED-6 recommendation: option (a)** — rotate the Tauri keypair *and* wire the
   CI gate. Rotation is nearly free (nothing shipped), and the CI gate must land
   before any public push.

---

## 1. History scan results

### 1.1 Method (three independent techniques)

- **Filename scan** — every file ever *added* on any ref:
  `git log --all --diff-filter=A --name-only`.
- **Blob provenance** — `git log --all --find-object=<blob>` +
  `git log --all --oneline -- <path>`.
- **Content sweep** — every blob reachable from all refs (deduped), scanned once:
  `git rev-list --all --objects | … | git cat-file --batch | <regex>`. Run in two
  size bands (`< 1 MiB` and `≥ 1 MiB` up to 26 MB) so binary-detected key files
  (invisible to a `git log -p` diff grep) are not missed. Big blobs (61 MB daemon
  binaries, etc.) were characterized by path.
- Corpus size: **1,824 commits across 21 refs** (incl. `refs/stash` and the
  `pre-sourceprep-rename` / `pre-rename-backup` tags).

No `gitleaks`/`trufflehog` on this machine; native tooling only (read-only, no
installs).

### 1.2 The one real secret

| Field | Value |
|---|---|
| Path (origin/main) | `src/prep/dashboard/src-tauri/.tauri/codrag.key` |
| Blob | `aad7cecc6fcac3371fa70ef932f80e0e88d699b7` (348 bytes) |
| Public half | `src/prep/dashboard/src-tauri/.tauri/codrag.key.pub` (blob `82ee42f6…`, 152 bytes) |
| Introduced | commit `5ba42227` (2026-04-21, Eric Bintner) |
| Modified since | **never** — `--find-object` returns only `5ba42227`; `git log -- <path>` = one commit |
| On refs (current tree) | `main`, `origin/main`, `deep-research/security`, `docs/feedback-concept-pipeline-audit-2026-07-11`, `magneticanomaly-footer-5apps`, `phase06-teams-sync-revive`, 3× `worktree-*`, `origin/*` counterparts, `refs/stash`, tag `pre-sourceprep-rename` |
| Format | base64 blob starting `dW50cnVzdGVkIGNvbW1lbnQ6` ("untrusted comment:"), which decodes to `untrusted comment: rsign encrypted secret key` → a **password-encrypted minisign/rsign Ed25519** secret key (Tauri v1 updater format) |

**Detection note (matters for the gate):** the on-disk `codrag.key` is base64 and
carries **no** plaintext `-----BEGIN … PRIVATE KEY-----` / `rsign` marker in its
raw bytes. A content-only secret grep (like the one suggested in the handoff)
would **not** catch it — it is caught by **filename/path** only. This is why the
mirror gate correctly denylists `codrag.key` / `*.key` by *path* (see §2), not by
content regex.

### 1.3 Every other secret-marker hit — enumerated and classified (all NOISE)

The `.key`/`.pub` filename scan returns **only** `codrag.key` and `codrag.key.pub`
— no other private-key *file* has ever existed in history. The content sweep's 20
marker-bearing blobs collapse to **7 distinct files**, each a false positive:

| File (`commit:file:line`) | Marker | Classification |
|---|---|---|
| `engine/crates/prep-sanitize/src/lib.rs:296` | `-----BEGIN RSA PRIVATE KEY-----` | **unit-test literal** — inside `#[test] fn test_detects_private_key_header()`; the value is literally `"-----BEGIN RSA PRIVATE KEY-----\ndata here"` |
| `engine/crates/prep-sanitize/src/lib.rs:275` | `AKIAIOSFODNN7EXAMPLE` | AWS's own docs example key, in a test |
| `engine/crates/prep-sanitize/src/lib.rs:282` | `ghp_ABCDEF…ghij` | sequential-alphabet placeholder, in a test |
| `engine/crates/codrag-sanitize/src/lib.rs` (pre-rename copy) | RSA / AKIA / ghp | same fixtures under the old crate name; not on origin/main HEAD (renamed to `prep-sanitize`) |
| `tests/test_remote_sync.py:155` | `AKIA1234567890ABCDEF` | dummy `"access_key"` test value |
| `docs/Phase06_Team_And_Enterprise/TEAM_SYNC_TEST_PLAN.md:220` | `AKIAIOSFODNN7EXAMPLE` | AWS docs example in a test plan |
| `docs/Phase142_OSS-First/AUDIT_VERIFICATION_2026-07-17.md:106` | `rsign encrypted secret key` | the audit doc **quoting** codrag.key's format string |
| `docs/Phase142_OSS-First/legal-security-message-audit.workflow.js` | `BEGIN OPENSSH PRIVATE KEY` | a **detection regex** literal inside audit tooling |
| `docs/Phase142_OSS-First/PUBLIC_MIRROR_MANIFEST_2026-07-19.json` | RSA / AKIA / ghp | the gate's own recorded **flagged-samples** output |

`akiazurewheatbeigeli` appeared under case-insensitive matching only — lowercase,
not a real AWS key id (real keys are `AKIA` + 16 **uppercase** alphanumerics).

### 1.4 Committed daemon-state / trace artifacts — scanned, no real credentials

History carries a large amount of accidentally-committed local state (dead-codename
`.codrag/` + `codrag_data/`, removed at the root in Phase-16 `5a748935`, plus
`src/codrag_data/` still tracked — see §7). The highest-risk of these, the settings
database, was scanned exhaustively:

- **186 distinct `codrag_settings.db` blob versions** (0.03–20 MB) — scanned all
  for `Bearer`/JWT (`eyJ…`)/`sk-ant`/`sk-proj`/`sk-…{32}`/`ghp_`/`github_pat_`/
  `[sr]k_live_`/real `AKIA`/`xox*`: **zero real credentials** (only the excluded
  fixtures).
- **14 `concurrency_trace_*.jsonl` request-trace logs** (~20 MB each) — same scan:
  **zero auth tokens**.
- `.env.example` and `docs/Phase11_Deployment/guides/01-accounts-credentials.md`
  (the only two files matching a "secret-ish filename" pattern besides the key):
  their **entire history diff** contains no real secret values — placeholders/prose
  only.

**§1 conclusion:** ✅ **`codrag.key` is the only real secret/private-key file in
git history.** No AWS/GitHub/Slack/Stripe/OpenAI/Anthropic/Lemon-Squeezy live
credential, no other PEM/OpenSSH/minisign private key, exists anywhere in
history — reachable, packed, stashed, or tagged.

---

## 2. Public-mirror gate state

### 2.1 CI-wired? **No — manual operator script only.** (folds into ED-6)

`git grep build_public_mirror` + a sweep of every automation surface returns hits
**only** in the script's own docstring and in `docs/Phase142_OSS-First/*` /
`docs/Phase144_LegalPreLaunch/*` planning docs. Confirmed absent from:

- `.github/workflows/*.yml` — all 8 (`deploy-websites`, `docker-headless`,
  `engine-wheels`, `license-audit`, `phase139-embedder-smoke`, `release`,
  `security-audit`, `websites-ci`). None invokes the gate; none pushes repo source
  to a public git mirror.
- `scripts/*`, `pyproject.toml` `[project.scripts]` (only `prep = prep.cli:main`),
  root `package.json` "scripts", `turbo.json` tasks.
- No `Makefile`/`*.mk`/`justfile`/`Taskfile`/`tox.ini`/`noxfile.py` exist.
- No git hooks: `.git/hooks/` has only `*.sample`; `core.hooksPath` default; no
  `husky`/`lefthook`/`.pre-commit-config.yaml` tracked.

⇒ **Nothing mechanically forces the gate before a publish.** It runs only when an
operator remembers to run it.

### 2.2 ⚠️ Ungated publish paths that bypass the gate entirely

`scripts/publish_deploy_subtree.sh` and `scripts/publish_prep_mcp_subtree.sh` each
do `git subtree split --prefix public/sourceprep-{deploy,mcp}` then
`git push <public-remote> <split>:refs/heads/main` (with `--promote`, to
`git@github.com:MagneticAnomaly/SourcePrep-deploy.git` and the MCP counterpart).
They **do not** call `build_public_mirror.py` and run **no content gate**. Scope
caveats: (1) they publish only the already-public `public/sourceprep-*` subtrees
(not the whole repo) to *separate* storefront-adjacent repos, not the main
`MagneticAnomaly/SourcePrep` mirror; (2) they are **not** CI-wired — they exist
only as hand-run commands in `HANDOFF.md` + docs. **Residual risk:** they use
`subtree split` (carries the **full commit history** of those subtrees, no
fresh-init), so any secret ever committed under `public/sourceprep-*` would leak.
The main storefront has *no* automated publish path — it is only ever produced by
the manual `build_public_mirror.py --emit` → `git init` flow.

### 2.3 Fresh-initial-commit — confirmed (origin history is never published by the mirror)

`tools/build_public_mirror.py` walks the **live tree** via `os.walk(REPO_ROOT)`
(`:326`) and copies only allowlisted files with `shutil.copy2` (`:429-434`). `.git`
is **triply** blocked: (1) in `HARD_PRUNE_DIRS` (`:280`), stripped from the walk at
`:332` so `os.walk` never descends into it; (2) not allowlisted, so `path_allowed`
is False (`:215-227`, `.git` absent from `ALLOW_TOP` `:62-98`) → dropped at `:351`;
(3) never enters `included`, so the emit loop (`:429`) can't copy it. The operator
then runs `git init` in the target (`:436`) → the mirror is a **brand-new repo with
no ancestry**. With `--emit --force`, any pre-existing `.git` in the target is
`shutil.rmtree`'d first (`:426`). **⇒ origin history — which holds blob `aad7cecc`
— can never reach a mirror produced by this script.** (This says nothing about
someone pushing the *workshop* repo directly; that path is out of the script's
control — see §2.5.)

### 2.4 Fail-closed — confirmed

`collect()` returns `(included, excluded, flagged)`; `main()` prints counts and, if
`flagged` is non-empty, prints `FAIL` and **`return 1`** at `:414-418`, placed
**before** the entire `if args.emit:` copy block (`:420-436`). A content hit aborts
with exit 1 and never reaches the copy loop; `:416-417` additionally refuse to
emit. `--force` (`:385`) only governs overwriting the target dir and cannot bypass
the gate. `codrag.key` specifically is caught by **exclusion** (path denylist
`codrag.key` / `*.key` / `*.pem`, `:150-152`; empirically `path_denied('…/.tauri/
codrag.key') == ['codrag.key','*.key']`), *before* content scan — plus the content
gate flags the `codrag.key` filename string (`:181`) and PEM markers (`:183-184`)
in any *other* included file as a backstop.

> Line-number note: the audit/handoff cite the fail-closed block as `:412-416`; in
> the current file it is `:414-418` (`:406-412` is the manifest write). Minor drift,
> same logic.

### 2.5 Two defense-in-depth gaps (from the adversarial gate read — product feedback, not active leaks)

Neither leaks the *current* `codrag.key` (the path denylist catches it solidly),
but both weaken the "path denylist **+** content gate" framing:

1. **The content gate does not backstop base64/DER keys.** `codrag.key`'s bytes
   contain 0 PEM markers, so the private-key regexes (`:183-184`, PEM-armor-only)
   would **not** flag it. For this secret type the **path denylist is the only
   effective layer**. A secret renamed off `.key`/`.pem` under an allowlisted top
   would evade both; so would a `> 2 MiB` file (content scan skipped,
   `CONTENT_SCAN_MAX_BYTES` `:262-263` → treated clean → included), a `BINARY_EXTS`
   extension (`:256-257`), or a file that raises `OSError` on read (`:260-267`
   swallow → clean).
2. **Self-scan exemption ships the dead codename.** The script exempts itself from
   the content gate (`:357-358`) and stays in `included`, so the emitted mirror
   carries `tools/build_public_mirror.py` containing the literal strings `codrag`
   and `codrag.key` (`:24,150,178,181`) — the exact markers it scrubs elsewhere.
   Recommend scrubbing/templating those literals or excluding the script from the
   mirror.

---

## 3. The two keys — do not conflate

| | **This session's key** | **Out of scope (Phase 146)** |
|---|---|---|
| Name | `codrag.key` (Tauri **updater** signing key) | `DEFAULT_PUBLIC_KEY_HEX`, `licensing.py:22` |
| Purpose | Signs macOS/Windows **app-update bundles**; the app verifies updates against the baked-in pubkey | Verifies **license keys** (JWT-like `payload.signature`) |
| Private/public | Private = `.tauri/codrag.key` (leaked); public = `.tauri/codrag.key.pub` + inlined at `tauri.conf.json:66`; key-id `C43F6BF18AEA1FE0` | The hex is a **public** key; value `3b6a27bc…59da29` is the RFC 8032 §7.1 Test-1 Ed25519 **public** key |
| Risk | Whoever holds the private key could sign a malicious app update **iff** they can also serve the updater endpoint | **License forgery** — the matching RFC-8032 test *private* key is world-known, so anyone can mint valid licenses |
| Fix | **Rotate** (this doc, §4) | Replace the placeholder with a real keypair (Phase 146 `CHANGE_PLAN_ed25519_crypto_fix.md`) — **not addressed here** |

The rotation plan below addresses **only** the Tauri updater key.

---

## 4. Rotation plan (ED-6 — research only; DO NOT execute)

Tauri version is **v1** (`src/prep/dashboard/src-tauri/Cargo.toml:10,13` →
`tauri`/`tauri-build = "1"`; `tauri.conf.json` uses the v1 top-level
`"tauri":{"updater":…}` shape, no `$schema`/`"plugins"`). Use v1 commands.

**Because no signed release was ever shipped (§6), the deprecation window is MOOT.**
The essential act is rotation (so the leaked key becomes powerless) + making the new
private key un-committable. History scrub is optional cleanup.

### Step 1 — Generate a new updater keypair (Eric, local)
```bash
cd src/prep/dashboard
# v1 CLI (npm) — prompts for a password that encrypts the private key at rest:
npx @tauri-apps/cli@^1 signer generate -w src-tauri/.tauri/updater.key
#   or: cargo tauri signer generate -w src-tauri/.tauri/updater.key
```
Recommend generating to a **new, codename-free name** (`updater.key` /
`updater.key.pub`) so rotation also kills the dead codename in one act. Outputs:
`updater.key` (SECRET — encrypted) and `updater.key.pub` (public).

**Where the private key lives:** NOT in the repo. Keep `updater.key` outside the
tree (e.g. a password manager) and store it as the GitHub Actions secret used by
`release.yml` (Step 3). Add `src-tauri/.tauri/*.key` to `.gitignore` and
`git rm --cached` the old `codrag.key` (see Step 5). The `.pub` is safe to commit.

### Step 2 — Publish the new public key (safe to commit)
- Replace the inlined base64 string at **`src/prep/dashboard/src-tauri/tauri.conf.json:66`** (`updater.pubkey`) with the contents of `updater.key.pub`.
- Commit `updater.key.pub` (or overwrite `codrag.key.pub`) — the public half only.

### Step 3 — Sign the next release with the new key
Release signing is CI at **`.github/workflows/release.yml:113-114`**, which maps
repo secrets → the v1 env vars the CLI reads:
`TAURI_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}` and
`TAURI_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_KEY_PASSWORD }}`.
⇒ Update those two **GitHub repo secrets** to the new private key + password. No
workflow code change needed (env-var names already correct for v1).

### Step 4 — Deprecate the old key
- **Here (nothing shipped): trivial.** No installed app trusts the old pubkey, so
  simply stop using it — the old key is dead the moment `tauri.conf.json:66` and the
  CI secrets are swapped.
- **General case (had a release shipped):** an installed v1 app verifies updates
  against the pubkey it shipped with, and v1 has no native multi-key rollover, so
  you would first ship a transitional release **signed by the OLD key** that carries
  the NEW pubkey, wait a full update cycle for the fleet to adopt it, then cut
  new-key-only releases. **Confirm with `gh release list -R MagneticAnomaly/SourcePrep`** (10 s) before assuming "nothing shipped."

### Step 5 — Scrub the old `codrag.key` from origin history (optional / deferred)
- **Untrack now (cheap, do this regardless):** `git rm --cached
  src/prep/dashboard/src-tauri/.tauri/codrag.key`, add `*.key` to `.gitignore`,
  commit.
- **History rewrite (heavy, low urgency):** `git filter-repo --path
  src/prep/dashboard/src-tauri/.tauri/codrag.key --invert-paths` (or BFG). This
  **rewrites history** → coordinated force-push + re-clone by every clone/worktree,
  and invalidates the `pre-sourceprep-rename` / `pre-rename-backup` tags. **Low
  urgency because:** the workshop repo is private and the mirror is fresh-init
  (history never publishes). Once the key is *rotated*, the leaked copy is powerless,
  so the scrub becomes cosmetic. Sequence it (if at all) with the §7 history-bloat
  cleanup, not as an emergency.

---

## 5. CI-gate plan (proposal — NOT applied; `.github/workflows/` untouched)

Two layers, because the gate has two jobs: keep mirror-failing content off `main`,
and gate the actual publish.

### 5a — Required CI check on the workshop repo
New `.github/workflows/public-mirror-gate.yml` (proposal):
```yaml
name: public-mirror-gate
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
jobs:
  mirror-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      # Dry-run: exit 1 on ANY content denylist hit (secret, dead codename, internal doc).
      - name: Public-mirror denylist gate
        run: python tools/build_public_mirror.py
```
Then mark `mirror-gate` a **required status check** in branch protection so no
commit that would fail the mirror can land on `main`.

### 5b — Gate the actual publish paths
- `build_public_mirror.py --emit` already fails closed (§2.4) — keep the manual
  emit flow as the *only* way to build the main mirror.
- **Fix the two subtree publishers (§2.2):** either replace
  `scripts/publish_{deploy,prep_mcp}_subtree.sh` with a `build_public_mirror`-style
  fresh-init emit, or add a mandatory `python tools/build_public_mirror.py` (or a
  scoped content-gate over `public/sourceprep-*`) as a pre-push step inside those
  scripts. As written they carry full subtree history with no gate.
- **Optional local backstop:** a committed `scripts/pre-push-mirror-gate.sh` that
  runs the dry-run gate, documented for `git config core.hooksPath` opt-in (local
  hooks are not enforced, so this is a convenience, not the guarantee — 5a is).

### 5c — Close the path-coverage gaps the gate audit found (§2.5, §7)
Add to `DENY_PATH_GLOBS`: `codrag_data`, `*/codrag_data`, `*.db`, `*.db-wal`,
`*.db-shm` (and scrub/exclude the self-referential codename strings in the shipped
script). This makes the settings-DB state (§7) mirror-excluded and makes the path
denylist cover the `.db` state class the content gate can't see.

---

## 6. Framed ED-6 decision

**Question:** (a) rotate the Tauri updater keypair *and* wire the mirror gate into
CI; (b) wire the CI gate only, defer rotation; (c) status quo.

**Key facts for the call:**
- `codrag.key` is a real leaked private key on origin, but it is the **updater**
  key, not the license key, and its blast radius requires also controlling the
  updater endpoint.
- **EVER-SHIPPED = no** — no `app-v*` tag exists, `release.yml:145` sets
  `releaseDraft: true`, and no `latest.json` is present. So **rotation is trivial**
  (no stranded installs, no deprecation window). *(Confirm the GitHub side with
  `gh release list -R MagneticAnomaly/SourcePrep`.)*
- The gate works but is manual, and there are ungated subtree-publish paths.

**Recommended default: (a) — do both.**
Rotation is nearly free precisely because nothing shipped, and it turns the
historical leak into a dead artifact; deferring it (option b) leaves a live signing
key on origin for no upside. The CI gate (5a) must land **before any public push**
regardless. Sequence: wire 5a → rotate (§4 Steps 1-3) → untrack old key (§4 Step 5
cheap half) → fix subtree publishers (5b) + path denylist (5c). Defer the history
rewrite (§4 Step 5 heavy half) to the §7 cleanup.

---

## 7. Additional in-scope finding — committed daemon state ships in the mirror

Surfaced while confirming §1; belongs with ED-6 / the mirror hardening.

- **On `origin/main` HEAD right now:** `src/codrag_data/codrag_settings.db`
  (0 bytes, git empty-blob `e69de29b`) and `src/codrag_data/ui_config.json`
  (1,648 bytes, blob `23884222`).
- **The gate would ship them.** Importing the gate module and evaluating both paths:
  `path_allowed = True` (under allowlisted `src`), `path_denied = []` (no
  `codrag_data`/`*.db`/`ui_config` denylist entry), `content_hits = []` ⇒
  **NET DISPOSITION: INCLUDED**. The **last manifest already lists both as included**
  (`docs/Phase142_OSS-First/PUBLIC_MIRROR_MANIFEST_2026-07-19.json:1559-1560`). So a
  mirror emit today publishes the dead-codename path `codrag_data/codrag_settings`
  — the exact thing the gate exists to prevent. The content gate can't stop it
  (it scans content, not paths; the `.db` is 0 bytes / `ui_config.json` has no
  `codrag` string).
- **No secret exposure.** `ui_config.json` is a benign default (`repo_root:""`,
  empty roots, one default Ollama `localhost:11434` endpoint, **no keys, no local
  paths, no other project names**); the `.db` is empty. This is a **dead-codename +
  hygiene** issue, not a secret leak.
- **History bloat:** `codrag_settings.db` was re-committed **186 times** at
  0.03–20 MB each (daemon-state churn) — a major contributor to workshop-repo size.
  The fresh-init mirror does not carry history, so this bloat never reaches the
  public repo; it only affects private-repo clone size.

**Recommended (Eric):** `git rm --cached src/codrag_data/codrag_settings.db
src/codrag_data/ui_config.json`, add `src/codrag_data/` + `*.db` to `.gitignore`
and to `DENY_PATH_GLOBS` (5c). Fold the 186-version history bloat into the same
optional history-rewrite pass as §4 Step 5 (heavy). Other dead-codename paths on
origin/main are already handled: `.claude/skills/codrag.md` (mirror-pruned),
`tests/test_no_cwd_relative_codrag_data.py` (content-flagged test), 20 `docs/`
paths (path-denied by `docs/Phase*`), `codrag.key`/`.pub` (path-denied).

---

## 8. Compliance / what this session did NOT do

Read-only, per the handoff hard rules: **no** key generated, **no** key rotated,
**no** history rewritten, **no** force-push, **no** file edited except this findings
doc, **no** `.github/workflows/` modified (5a/5b/5c are *proposals*), **no** attorney
act, **no** license assertion. Git touched only via read commands
(`log`/`show`/`rev-list`/`cat-file`/`ls-tree`/`ls-files`/`for-each-ref`/`find-object`).
The protected `stash@{0}` was read (`ls-tree`) but never modified. The `codrag.key`
*file* was NOT renamed (a release-engineering act Eric sequences with rotation) —
only flagged.

### Dogfooding note (prep MCP)
`prep` returned a thin atlas centered on the Phase 136/145 pipeline focus areas —
of little use for a git-history/secret/Tauri task, which is **expected**: git
history is outside prep's graph (the handoff said so), and codebase-structure
context doesn't cover committed-secret or dead-codename-path concerns. Not a bug,
but a genuine improvement idea: the immune system could grow an antibody for
"daemon state / `*.db` committed under a source path" and "dead-codename in a
tracked path" — both are structural signals prep *could* surface, and both are
exactly what this session had to find by hand.
