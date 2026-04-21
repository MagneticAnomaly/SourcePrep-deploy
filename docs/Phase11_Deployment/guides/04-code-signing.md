# Guide: Code Signing — macOS & Windows

> **Prerequisite:** ACC-1 (Apple Developer Program) and ACC-4 (Windows EV cert) must be
> complete before these steps. This guide covers configuring the certs for use in CI.

---

## macOS: Developer ID Signing + Notarization (TAU-3, TAU-4)

### Step 1 — Download your Developer ID certificate

1. Go to [developer.apple.com/account/resources/certificates](https://developer.apple.com/account/resources/certificates/)
2. Click **+** to create a new certificate
3. Choose **Developer ID Application** (not "Mac App Store" — that's for the App Store only)
4. You'll be prompted to upload a **Certificate Signing Request (CSR)**:
   - Open **Keychain Access** (search it in Spotlight)
   - Menu: **Keychain Access → Certificate Assistant → Request a Certificate from a Certificate Authority**
   - Enter your email, leave CA Email blank, choose **"Saved to disk"**
   - Save the `.certSigningRequest` file
5. Upload the CSR to Apple. Download the resulting `.cer` file.
6. Double-click the `.cer` file — it installs into your Keychain automatically
7. Open Keychain Access → **My Certificates** — you should see **"Developer ID Application: Magnetic Anomaly LLC (XXXXXXXXXX)"**

### Step 2 — Export cert for CI use

CI can't use your Keychain directly — you need to export the cert as a `.p12` (PKCS#12) file.

1. In Keychain Access → **My Certificates**, find the Developer ID Application cert
2. Right-click → **Export**
3. Choose format **Personal Information Exchange (.p12)**
4. Set a strong export password — save it in your password manager
5. Save as `developer-id.p12`

### Step 3 — Add cert to GitHub Secrets

1. Base64-encode the `.p12`:
   ```bash
   base64 -i developer-id.p12 | pbcopy
   ```
   (This copies the base64 string to clipboard)

2. Go to [github.com/MagneticAnomaly/Prep-MCP/settings/secrets/actions](https://github.com/MagneticAnomaly/Prep-MCP/settings/secrets/actions)
3. Add these secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `APPLE_CERTIFICATE` | Base64 string from step 1 |
   | `APPLE_CERTIFICATE_PASSWORD` | Export password from step 2 |
   | `APPLE_SIGNING_IDENTITY` | e.g., `Developer ID Application: Magnetic Anomaly LLC (XXXXXXXXXX)` |
   | `APPLE_ID` | Your Apple ID email |
   | `APPLE_ID_PASSWORD` | App-specific password (see Step 4) |
   | `APPLE_TEAM_ID` | Your 10-character Team ID from developer.apple.com |

### Step 4 — Create an app-specific password for notarization

Apple notarization requires your Apple ID credentials, but you should not use your main password.

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in → **Sign-In and Security → App-Specific Passwords**
3. Click **Generate an app-specific password**
4. Name it `prep-notarize`
5. Copy the generated password → add as `APPLE_ID_PASSWORD` in GitHub Secrets (step 3)

### Step 5 — (Optional) App Store Connect API key — more reliable for CI

App-specific passwords can be revoked. The App Store Connect API key is more stable for CI:

1. Go to [appstoreconnect.apple.com/access/api](https://appstoreconnect.apple.com/access/api)
2. Click **+** to generate a key, role: **Developer**
3. Download the `.p8` file (can only be downloaded once)
4. Note the **Key ID** and **Issuer ID**
5. Add to GitHub Secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `APPLE_API_KEY` | Contents of the `.p8` file |
   | `APPLE_API_KEY_ID` | Key ID |
   | `APPLE_API_ISSUER_ID` | Issuer ID |

> If using this approach, remove `APPLE_ID` and `APPLE_ID_PASSWORD` — they're not needed.

---

## macOS: Smoke Test (TAU-8)

After the first signed release build:

1. Download the `.dmg` from GitHub Releases onto a **separate Mac** (not your dev machine)
2. Or: right-click the `.dmg` → Open (to bypass Gatekeeper on the same machine)
3. Verify no "unverified developer" warning appears
4. Install the app, add a project, run a build, confirm search works
5. Check that the app doesn't request any unexpected permissions on first launch

---

## Windows: EV Code Signing (TAU-5)

### Option A: Azure Key Vault (recommended for CI)

This is the standard approach when your EV cert is stored in a cloud HSM.

1. In the Azure Portal, create a **Key Vault** (free tier is fine):
   - Portal → Create a resource → Key Vault
   - Name: `prep-signing`
   - Region: choose nearest

2. Your cert provider (DigiCert, Sectigo) will have given you instructions to import the cert
   into Key Vault — follow their guide to complete this

3. Create a service principal for CI access:
   ```bash
   az ad sp create-for-rbac --name prep-ci-signing --role "Key Vault Certificate User" \
     --scopes /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/prep-signing
   ```
   Note the `appId`, `password`, and `tenant` from the output

4. Add to GitHub Secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `AZURE_KEY_VAULT_URI` | e.g., `https://prep-signing.vault.azure.net/` |
   | `AZURE_CLIENT_ID` | `appId` from above |
   | `AZURE_CLIENT_SECRET` | `password` from above |
   | `AZURE_TENANT_ID` | `tenant` from above |
   | `AZURE_CERT_NAME` | Certificate name in Key Vault |

5. The Tauri release workflow will use `AzureSignTool` to sign — this is already handled
   in the CI workflow code once these secrets exist.

### Option B: SSL.com eSigner (simpler setup)

SSL.com offers a cloud signing service that's easier to integrate:

1. Purchase cert from [ssl.com/code-signing](https://www.ssl.com/code-signing/)
2. Enroll in **eSigner** cloud signing service
3. Add to GitHub Secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `ESIGNER_USERNAME` | SSL.com account username |
   | `ESIGNER_PASSWORD` | SSL.com account password |
   | `ESIGNER_TOTP_SECRET` | TOTP secret from eSigner setup |

---

## Windows: Smoke Test (TAU-8)

After the first signed Windows release:

1. Download the `.msi` on a **clean Windows VM** (Windows Sandbox works)
2. Run the installer — verify SmartScreen does **not** show a red warning
   - An EV cert should show a blue/green "Verified publisher" prompt with your company name
3. Install, add a project, run a build, confirm search works
4. Test uninstall via Add/Remove Programs — verify clean removal
