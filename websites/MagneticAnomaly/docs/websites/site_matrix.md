# Website Migration & SSL Matrix

This document tracks the status of various domains, their current hosting situation, and the required actions for SSL and DNS migration.

## 1. Immediate Action Required (GoDaddy Hosted)
These sites are actively hosted on GoDaddy and are in danger of failing if SSL is not updated immediately. The plan is to move their DNS to Cloudflare (setting A records to "Proxied") to provide free SSL, while keeping the hosting files on GoDaddy for now.

| Domain | Current Host | Next Step | Status |
| :--- | :--- | :--- | :--- |
| **stellarmusicspace.com** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |
| **samanthabassler.com** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |
| **ericbintner.com** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |
| **homecolab.app** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |
| **magneticanomaly.llc** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |
| **ismisms.com** | GoDaddy | Migrate DNS to Cloudflare | 🟢 Done |

*(Note: Ensure any `mail` MX records for these domains are set to "DNS Only" in Cloudflare during migration).*

---

## 2. Low Priority / Eventual Move (Currently Not Hosted or Placeholder)
These domains are registered but either not actively hosted or are just placeholders. Eventually, they will be moved to Cloudflare for DNS and services like Netlify/Vercel for static hosting.

| Domain | Current Host | Next Step | Status |
| :--- | :--- | :--- | :--- |
| magneticanomaly.com | None / GoDaddy Parked | Move DNS to CF, Host on Netlify | ⚪️ Unscheduled |
| dinner.vision | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| parleysocial.app | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| halley.chat | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| debate.haus | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| scottbintner.com | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| loveprogramm.org | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| ericbintner.net | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| stellarstretch.com | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |
| stellaryogaspace.com | None / GoDaddy Parked | Move DNS to CF | ⚪️ Unscheduled |

---

## 3. Hosted Elsewhere (No Action Needed)
These domains are already correctly configured on external platforms that handle SSL automatically.

| Domain | Current Host | Note | Status |
| :--- | :--- | :--- | :--- |
| codrag.io | Cloudflare | DNS & SSL already managed by CF. | 🟢 Good |
| missmasterscloset.com | Shopify | SSL managed automatically by Shopify. | 🟢 Good |

