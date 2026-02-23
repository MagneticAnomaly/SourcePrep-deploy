# Guide: VS Code Marketplace Publishing

> **Prerequisites:** VSC-1 through VSC-3 (packaging the extension) must be done first —
> I handle those. This guide covers only the manual steps to create a publisher account
> and submit the extension to the marketplace.

---

## Step 1 — Create an Azure DevOps organization

The VS Code Marketplace uses Azure DevOps for publisher authentication.

1. Go to [dev.azure.com](https://dev.azure.com)
2. Sign in with a Microsoft account (use the same one as ACC-5 / Microsoft Partner Center, or create one for Magnetic Anomaly LLC)
3. Create an organization:
   - Click **"Create new organization"**
   - Name: `magnetic-anomaly` (or similar)
   - Region: closest to you
4. You don't need to create any projects — just the organization

---

## Step 2 — Create a Personal Access Token (PAT)

1. In Azure DevOps, click your profile icon (top right) → **Personal access tokens**
2. Click **"New Token"**
3. Configure:
   - **Name:** `vsce-publish`
   - **Organization:** All accessible organizations
   - **Expiration:** 1 year
   - **Scopes:** Custom defined → **Marketplace → Manage** (check this specific scope)
4. Click **Create** → copy the token immediately (shown only once)
5. Save it in your password manager

---

## Step 3 — Create a VS Code Marketplace publisher

1. Go to [marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage)
2. Sign in with the same Microsoft account
3. Click **"Create publisher"**
4. Fill in:
   - **Publisher ID:** `magnetic-anomaly` (lowercase, no spaces — this appears in extension IDs)
   - **Display name:** `Magnetic Anomaly`
   - **Description:** Optional
5. Click **Create**

---

## Step 4 — Verify the publisher in `package.json`

The extension's `package.json` (at `packages/vscode/package.json`) must have:

```json
{
  "publisher": "magnetic-anomaly",
  "name": "codrag",
  ...
}
```

The full extension ID will be `magnetic-anomaly.codrag`. I can update this — just ask.

---

## Step 5 — Publish

Once VSC-3 (`.vsix` package) is ready:

### Option A: Publish via CLI

```bash
# Install vsce globally if not already
npm install -g @vscode/vsce

# Log in with your PAT
vsce login magnetic-anomaly
# Enter your PAT when prompted

# Publish (from the packages/vscode directory)
vsce publish
```

### Option B: Upload manually via the web

1. Go to [marketplace.visualstudio.com/manage/publishers/magnetic-anomaly](https://marketplace.visualstudio.com/manage/publishers/magnetic-anomaly)
2. Click **"New extension"** → **VS Code**
3. Upload the `.vsix` file

---

## Step 6 — Add GitHub Secret for CI publishing (optional)

To publish automatically from CI on a `vscode-v*` tag:

1. Go to [github.com/MagneticAnomaly/CoDRAG-MCP/settings/secrets/actions](https://github.com/MagneticAnomaly/CoDRAG-MCP/settings/secrets/actions)
2. Add:

   | Secret Name | Value |
   |-------------|-------|
   | `VSCE_PAT` | Your Azure DevOps PAT from Step 2 |

---

## Step 7 — Marketplace listing

After publishing, complete the marketplace listing:

1. Go to [marketplace.visualstudio.com/manage](https://marketplace.visualstudio.com/manage)
2. Click on **CoDRAG** → **Edit**
3. Add:
   - **Icon:** 128×128 PNG logo
   - **Screenshots:** At least 2–3 showing the extension in action
   - **Categories:** `Other` or `Programming Languages`
   - **Tags:** `AI`, `code search`, `context`, `RAG`
   - **Repository:** `https://github.com/MagneticAnomaly/CoDRAG-MCP`
   - **Bugs URL:** `https://support.codrag.io`

---

## Notes

- Extensions are reviewed by Microsoft — review typically takes a few hours for new submissions, faster for updates
- Version numbers must be incremented on every publish (`major.minor.patch`)
- Auto-update is handled by VS Code marketplace natively (VSC-5) — no work needed on your end
