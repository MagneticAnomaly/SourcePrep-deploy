# Handoff: Finish the SourcePrep rename push/publish

> **Purpose:** Instructions for a fresh AI session to pick up where the previous session left off on the RunPrep → SourcePrep rename and finish pushing/publishing.
>
> **Delete this file** (`git rm HANDOFF.md` if tracked, or just `rm`) once the work is done.

---

## TL;DR

- Branch `rename/runprep-to-sourceprep` is already pushed to `github.com:MagneticAnomaly/SourcePrep.git`.
- `main` is already pushed there too (at `1e066ffb` — baseline + spec commit).
- **Remaining work:** push a safety tag, open the PR, and populate the two empty subtree repos (`SourcePrep-MCP`, `SourcePrep-deploy`). Optional: Phase 9 verification.
- Previous session was **gated on `git push` by permission settings** — if you're running with push permissions enabled, just execute the commands. Otherwise surface them for the user.

---

## Working directory and state

```
Working dir: /Volumes/4TB-BAD/HumanAI/CoDRAG
Branch:      rename/runprep-to-sourceprep
Latest HEAD: 7d2134ea  ci: add Netlify deploy workflow for marketing/docs/support/payments sites
Main branch: main (at 1e066ffb locally, same on remote)
```

Start by running `git status`, `git remote -v`, and `git log --oneline -5` to confirm state.

## Remotes (already rewired)

All four point to `MagneticAnomaly/SourcePrep*`:

```
origin   git@github.com:MagneticAnomaly/SourcePrep.git
mcp      git@github.com:MagneticAnomaly/SourcePrep-MCP.git
mcp-dev  git@github.com:MagneticAnomaly/SourcePrep-MCP-DEV.git
deploy   git@github.com:MagneticAnomaly/SourcePrep-deploy.git
```

There is **no `deploy-dev` remote** — the plan mentions one but it was never configured. Ignore.

The old `MagneticAnomaly/RunPrep*` repos still exist on GitHub as the pre-rename history anchor; don't touch them.

## What's already pushed to `MagneticAnomaly/SourcePrep`

```
refs/heads/main                          1e066ffb (baseline e1d8191d + docs(spec))
refs/heads/rename/runprep-to-sourceprep  7d2134ea (all 34 rename commits)
```

## Local tag not yet pushed

```
pre-sourceprep-rename  -> e1d8191d (the trusted "rebrand" baseline on origin/main)
```

---

## Remaining tasks, in order

### 1. Push the safety tag

```bash
git push origin pre-sourceprep-rename
```

Expected output: `* [new tag] pre-sourceprep-rename -> pre-sourceprep-rename`.

### 2. Open the PR

`gh` CLI is **not installed** on this machine. Options:

**Option A — install gh and use it:**
```bash
brew install gh
gh auth login
gh pr create --base main --head rename/runprep-to-sourceprep \
  --title "rename: RunPrep -> SourcePrep brand sweep" \
  --body "$(cat <<'EOF'
## Summary
Full brand rename from RunPrep to SourcePrep. Code-level identifiers (Python package `prep`, CLI, MCP tool names like `prep_search`, VS Code command IDs `prep.*`, Rust crates `prep-*`, npm `@prep/*`, `PREP_*` env vars) are preserved per the brand/code split decision.

Back-compat paths (`.runprep/`, `~/.runprep/license.json`) are intentionally kept for users migrating from the previous name.

## Test plan
- [ ] `bash scripts/rename_gate.sh` passes (0 hits)
- [ ] `.venv/bin/pytest tests/test_paths.py tests/test_data_dir_migration.py -v` passes
- [ ] Daemon smoke: `prep serve --port 18400` creates `~/.local/share/sourceprep/`
- [ ] Tauri dev launch shows "SourcePrep" in window chrome

See plan: `docs/superpowers/plans/2026-04-22-sourceprep-rename-implementation.md`
EOF
)"
```

**Option B — open the PR in a browser:**
```bash
open 'https://github.com/MagneticAnomaly/SourcePrep/pull/new/rename/runprep-to-sourceprep'
```
Paste the same title + body manually.

### 3. Populate the public subtree repos

Both target repos (`SourcePrep-MCP`, `SourcePrep-deploy`) are currently empty.

The existing scripts use `git subtree split` which **walks all ~1023 repo commits** checking each for path touches. For `public/prep-mcp` and `public/prep-deploy` only **4 commits actually touch each prefix**, so a full split is overkill for a first release.

**Recommended: snapshot push** (fast, clean slate for a first public release):

```bash
# SourcePrep-MCP
repo_root=/Volumes/4TB-BAD/HumanAI/CoDRAG
tmp=$(mktemp -d)
cp -a "$repo_root/public/prep-mcp/." "$tmp/"
cd "$tmp"
git init -b main
git add -A
git commit -m "initial: SourcePrep MCP public distribution"
git remote add origin git@github.com:MagneticAnomaly/SourcePrep-MCP.git
git push -u origin main
cd "$repo_root"

# SourcePrep-deploy
tmp2=$(mktemp -d)
cp -a "$repo_root/public/prep-deploy/." "$tmp2/"
cd "$tmp2"
git init -b main
git add -A
git commit -m "initial: SourcePrep deploy distribution"
git remote add origin git@github.com:MagneticAnomaly/SourcePrep-deploy.git
git push -u origin main
cd "$repo_root"
```

Also push the mirror to `mcp-dev` once the snapshot is on `mcp`:
```bash
git -C "$repo_root" fetch mcp
# Fast-forward push mcp's main to mcp-dev
mcp_sha=$(git ls-remote mcp refs/heads/main | cut -f1)
git push mcp-dev "$mcp_sha:refs/heads/main"
```

**Alternative — full subtree history preservation** (takes 5-15 min, bash progress `N/1023 (M)` is normal, NOT a hang):

```bash
scripts/publish_prep_mcp_subtree.sh --promote      # pushes to mcp-dev and mcp
scripts/publish_deploy_subtree.sh --promote        # pushes to deploy
```

If you choose subtree and it looks stuck, verify it's alive via `ps aux | grep git-subtree` in another terminal.

### 4. (Optional) Phase 9 verification

From the plan's §9 — not strictly required for the rename to be "done" but good practice before declaring shippable:

```bash
# 9.1 Rename gate (already known to pass)
bash scripts/rename_gate.sh                       # expect exit 0, no output

# 9.2 Targeted pytest
.venv/bin/pytest tests/test_paths.py tests/test_data_dir_migration.py \
                 tests/test_l3_plumbing.py tests/test_configure_concept_store_init.py -v
# Expected: green. Two TestLicenseFromEnv failures exist and are ENVIRONMENTAL
# (user's real license at ~/.runprep/license.json leaks into tests) — flag, don't fix.

# 9.4 Typechecks
cd packages/vscode && npm run typecheck && cd -
cd packages/ui && npm run typecheck && cd -
# Expected: green.

# 9.6 Daemon smoke
.venv/bin/prep serve --port 18400 &
sleep 3
curl -s http://localhost:18400/health
ls -la ~/.local/share/sourceprep/ | head     # expect this dir created
kill %1
```

Phase 9.7 (Tauri visual check) is manual and can wait until after merge.

---

## Known issues and constraints

### Permission gating
The previous session had `git push` denied by `Permission to use Bash` — same command worked when the user ran it in their own terminal. If you hit the same wall, surface the exact command for the user and move on. Don't assume you have broader permissions than the previous session.

### Desktop folder is off-limits
The shell this AI runs in does not have macOS TCC grants for `~/Desktop`. If the user references files there, ask them to copy to `/tmp/` or the repo root. Don't spin on `Operation not permitted`.

### Large files in git history
Push output includes warnings for 3 daemon binaries >50MB:
- `src/prep/dashboard/src-tauri/binaries/prep-daemon-aarch64-apple-darwin` (61 MB)
- `src/prep/dashboard/src-tauri/binaries/prep-daemon-x86_64-apple-darwin` (59 MB)
- `src/codrag/dashboard/src-tauri/binaries/codrag-daemon-aarch64-apple-darwin` (54 MB, historical)

**These are NOT failures.** GitHub just nudges toward LFS. The push succeeds. Don't try to fix unless the user explicitly asks (it requires history rewrite or LFS migration — out of scope for the rename).

### `.runprep/` path literals are kept on purpose
Back-compat: `_LICENSE_PATH = Path.home() / ".runprep" / "license.json"` and the walker exclude `**/.runprep/**` are allowlisted in `.rename-allowlist.txt`. Do not "fix" these — they let existing users keep working.

### 2 environmental test failures
`tests/test_feature_gate.py::TestLicenseFromEnv::{test_no_env_defaults_to_free, test_env_invalid_falls_back_to_free}` fail because the test doesn't mock the filesystem license lookup and Eric's real perpetual license at `~/.runprep/license.json` is loaded. Pre-existing test-isolation bug, NOT caused by the rename. Report and move on.

### Nested worktree
`.claude/worktrees/busy-swirles/` is a separate git workspace. `git status` in the main repo always shows it as untracked — that's expected, leave it alone.

### Shell cwd drift
`cd` changes persist across Bash tool calls in a session. After entering `.claude/worktrees/busy-swirles` or `/tmp/`, subsequent commands run there. Use absolute paths (`/Volumes/4TB-BAD/HumanAI/CoDRAG/...`) or `cd` back explicitly.

---

## Plan file

Full 65KB implementation plan: `docs/superpowers/plans/2026-04-22-sourceprep-rename-implementation.md`.
All tasks through Phase 6.1 are committed. Phase 7-8 already partly executed (remotes rewired, main+branch pushed). Phase 8.1 tag is created locally, not pushed. Phase 9 is the verification suite above.

## Safety anchor

If anything goes wrong, the pre-rename state is:
- OLD remotes still exist: `github.com:MagneticAnomaly/RunPrep.git` et al
- Local tag `pre-sourceprep-rename` points at `e1d8191d` (the trusted baseline)
- Branch `rename/runprep-to-sourceprep` is separate from `main` — merging is reversible
