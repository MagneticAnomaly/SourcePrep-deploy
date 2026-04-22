# Deferred Setup: Support & Payments Sites

This document contains the specific runtime configurations required for the **Support** and **Payments** sites. Because these apps rely on external APIs and server-side routes, they must have their environment variables configured in the Netlify UI *before* they are fully deployed.

Once you are ready to launch these two sites, follow the steps below.

---

## 1. Configure Netlify Environment Variables

Go to your Netlify Dashboard → Select the specific project (e.g., `sourceprep-support`) → **Site configuration** → **Environment variables** → **Add a variable**.

*(Note: Check "Contains secret values" for sensitive keys like API tokens so they are masked in the UI).*

### Support Site (`sourceprep-support`)
Add the following variables:

| Key | Value / Source | Secret? |
|-----|----------------|---------|
| `NEXT_PUBLIC_SITE_URL` | `https://support.sourceprep.io` | No |
| `GITHUB_TOKEN` | Fine-grained PAT with read-only Discussions access. (Go to GitHub Settings → Developer Settings → Personal access tokens → Fine-grained tokens. Grant Read-only to Discussions for `MagneticAnomaly/SourcePrep`). | Yes |
| `RESEND_API_KEY` | From your Resend.com dashboard (used for bug report emails). | Yes |
| `BUG_REPORT_EMAIL` | `bugs@sourceprep.io` | No |

### Payments Site (`sourceprep-payments`)
Add the following variables:

| Key | Value / Source | Secret? |
|-----|----------------|---------|
| `NEXT_PUBLIC_SITE_URL` | `https://payments.sourceprep.io` | No |
| `NEXT_PUBLIC_RUNPREP_CHECKOUT_URL` | Your Lemon Squeezy checkout URL. | No |
| `LEMONSQUEEZY_API_KEY` | From Lemon Squeezy Dashboard → Settings → API. | Yes |
| `LEMONSQUEEZY_STORE_ID` | From Lemon Squeezy Dashboard → Settings → Stores. | No |

---

## 2. Re-Enable GitHub Actions Deployment

Currently, the `deploy-support` and `deploy-payments` jobs are commented out in `.github/workflows/deploy-websites.yml` to prevent them from deploying without proper configuration.

When you are ready to deploy them:
1. Open `.github/workflows/deploy-websites.yml`.
2. Uncomment the `deploy-support` and `deploy-payments` jobs at the bottom of the file.
3. Commit and push the changes to `main`.

GitHub Actions will then build and deploy them alongside Marketing and Docs!

---

## 3. Map Custom Domains & DNS

After the first successful deployment:
1. In Netlify, go to **Domain management** for each project and add the custom domains (`support.sourceprep.io` and `payments.sourceprep.io`).
2. In Cloudflare, add the corresponding **CNAME** records pointing `support` and `payments` to their respective `.netlify.app` URLs (ensure the Orange Cloud / Proxy is enabled).
