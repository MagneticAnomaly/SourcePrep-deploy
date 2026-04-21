# Guide: Microsoft Store Submission

> **Prerequisites:**
> - ACC-5 (Microsoft Partner Center account) — must be approved
> - TAU-5 (Windows code signing) — installer must be signed
> - TAU-7 (release artifacts) — `.msi` or `.exe` must exist
>
> **Note:** This is a post-launch task. Complete direct distribution (GitHub Releases) first.

---

## MST-1 — Register the product in Partner Center

1. Go to [partner.microsoft.com/dashboard](https://partner.microsoft.com/dashboard)
2. Sign in with Magnetic Anomaly LLC account
3. Click **"Windows & Xbox"** → **"Overview"**
4. Click **"Create a new app"**
5. Enter the app name: **Prep**
6. Click **Reserve product name** — this reserves "Prep" in the store

---

## MST-2 — Configure as EXE/MSI with external licensing

The Microsoft Store allows apps that use external payment/licensing (not Microsoft's IAP system),
but you must declare this in the submission.

1. In your product dashboard → **Pricing and availability**
2. Set:
   - **Markets:** All markets (or restrict as needed)
   - **Pricing:** Free (the app is free to install; licensing is handled externally by Lemon Squeezy)
3. In **Properties**:
   - **Category:** Productivity → Developer tools
   - **Sub-category:** Coding
4. In **Packages** (see MST-3) — make sure your package type is EXE or MSI (not MSIX)
5. Per **MS Store Policy 10.8.1**: apps using external purchase mechanisms must not use
   in-app purchase UI that resembles Microsoft's system. Our Lemon Squeezy flow is a
   web-based checkout, which is compliant.

---

## MST-3 — Submit the code-signed installer

1. In your product dashboard → **Packages**
2. Click **"Add packages"**
3. Upload your signed `.msi` or `.exe` from GitHub Releases (TAU-7)
   - The package must be signed with your EV cert (ACC-4)
   - Microsoft runs their own scan — a signed EV cert significantly reduces rejection risk
4. Fill in the **supported architectures**: x64 (required), ARM64 (if you have an ARM build)
5. Set **minimum OS version**: Windows 10 version 1903 or later (recommended)

---

## MST-4 — Store listing: screenshots, description, category

1. In your product dashboard → **Store listings** → **English (United States)**
2. Fill in:

   **Description** (up to 10,000 characters):
   > Prep enriches your AI coding assistant with structural code context — imports,
   > call graphs, symbol hierarchies, and dependency chains. Works with Cursor, Windsurf,
   > VS Code, Claude Desktop, and any MCP-compatible tool.

   **Short description** (up to 270 characters):
   > Structural code context for AI. Indexes your codebase into a knowledge graph that
   > supercharges Cursor, Windsurf, and other AI coding tools.

   **Screenshots:** At least 4 required, recommended size 1366×768 or larger
   - Take screenshots of: dashboard, search results, MCP integration in action, settings
   - Use clean, professional screenshots — no personal data visible

   **App features** (bullet points):
   - Structural code graph (imports, calls, symbols)
   - Semantic search across your codebase
   - MCP server — integrates with Cursor, Windsurf, VS Code, Claude
   - Native embeddings — no external API needed
   - Offline-first — works without internet

   **Keywords (search terms):**
   `AI coding, code search, RAG, MCP, Cursor, Windsurf, code graph, developer tools`

3. Upload the **app icon** (300×300 PNG minimum, transparent background recommended)

---

## MST-5 — Test the Store install flow

After submission is approved (usually 1–3 business days for new apps):

1. Install from the Microsoft Store on a clean Windows machine (or Windows Sandbox)
2. Verify:
   - [ ] App installs without warnings
   - [ ] App launches correctly
   - [ ] License activation via Lemon Squeezy works (web checkout opens in browser)
   - [ ] After purchase, features unlock in the app
   - [ ] App uninstalls cleanly via Store or Add/Remove Programs

---

## Submission timeline

| Stage | Typical time |
|-------|-------------|
| Initial review | 1–3 business days |
| Updates to existing app | Few hours – 1 day |
| Rejection appeal | Add 3–5 days |

## Common rejection reasons

- **Missing privacy policy URL** — add `https://runprep.io/privacy` to the listing
- **App crashes on launch** — always test on a clean VM before submission
- **External purchase not disclosed** — ensure the listing description mentions that licensing is handled externally
- **Unsigned or incorrectly signed package** — double-check EV cert is applied

## Privacy policy requirement

Microsoft requires a privacy policy URL. Add one to the listing:
- URL: `https://runprep.io/privacy`
- The marketing site needs a `/privacy` page if it doesn't have one yet
