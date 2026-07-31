# Portfolio "Mothership" Email Matrix

**Strategy:** The "Mothership" architecture routes all public-facing emails for portfolio apps through Cloudflare's free Email Routing. They are delivered to dedicated, siloed inboxes on the parent company domain (`magneticanomaly.llc`). 

**Why this works:**
1. **Cost & Limits:** This consumes only **1 Custom Domain** and **11 Email Addresses**, keeping you perfectly within the limits of Thundermail's $6/month Early Bird plan (which allows 3 domains and 15 addresses).
2. **M&A Readiness:** Every app has its own dedicated inbox on the parent domain. If an app is acquired, you simply export that specific Thunderbird inbox as a `.mbox` file and hand it to the buyer.
3. **Simplicity:** You only ever have to log into ONE email server (currently cPanel, eventually Thundermail). 

---

## The Master Routing Matrix

| Portfolio App | Public Email (What users see) | DNS Action (Cloudflare) | Mothership Inbox (Where it lives) | M&A Export Cleanliness |
| :--- | :--- | :--- | :--- | :--- |
| **Magnetic Anomaly** | `hello@magneticanomaly.llc` | Direct to cPanel/Thundermail | `hello@magneticanomaly.llc` | N/A (Parent Co) |
| **SourcePrep** | `support@sourceprep.io` | Forward | `sourceprep-support@magneticanomaly.llc` | High |
| | `enterprise@sourceprep.io` | Forward | `sourceprep-enterprise@magneticanomaly.llc` | High |
| | `licenses@sourceprep.io` | Forward | `sourceprep-licenses@magneticanomaly.llc` | High |
| | `security@sourceprep.io` | Forward | `sourceprep-security@magneticanomaly.llc` | High |
| | `bugs@sourceprep.io` | Forward | `sourceprep-bugs@magneticanomaly.llc` | High |
| **Applivation** | `support@applivation.app` | Forward | `applivation-support@magneticanomaly.llc` | High |
| **HomeColab** | `support@homecolab.app` | Forward* | `homecolab-support@magneticanomaly.llc` | High |
| | `privacy@homecolab.app` | Forward* | `homecolab-privacy@magneticanomaly.llc` | High |
| **DinnerVision** | `support@dinnervision.app` | Forward* | `dinnervision-support@magneticanomaly.llc` | High |
| **DebateHaus** | `beta@debatehaus.app` | Forward* | `debatehaus-beta@magneticanomaly.llc` | High |

*\*Requires moving DNS to Cloudflare first to enable forwarding.*

---

## Step-by-Step Implementation Guide

### Phase 1: Setup the Mothership (Right Now)
1. Log into your GoDaddy cPanel for `magneticanomaly.llc`.
2. Create the 11 specific email addresses listed in the **"Mothership Inbox"** column above. 
3. Open your Thunderbird Desktop App. Add `hello@magneticanomaly.llc` as your primary account. 
4. Add the other 10 addresses to Thunderbird. You now have a perfectly organized sidebar with every app's inbox separated.

### Phase 2: Setup the Routing (Right Now)
1. **For SourcePrep & Applivation:** Go into Cloudflare -> Email Routing. Forward the "Public Emails" to their corresponding "Mothership Inboxes". 
2. **For HomeColab:** Change NameServers in GoDaddy to point to Cloudflare. Once active, set up Email Routing to forward to the Mothership.
3. **For DinnerVision & DebateHaus:** Add the domains to Cloudflare, then set up Email Routing to forward to the Mothership.

### Phase 3: The Thundermail Cutover (Future)
When you get access to Thundermail:
1. Add **ONLY** `magneticanomaly.llc` to Thundermail. (Consumes 1 of 3 domain slots).
2. Create the 11 aliases inside Thundermail. (Consumes 11 of 15 address slots).
3. Open Thunderbird. Drag and drop the historical emails from the cPanel accounts to the new Thundermail accounts.
4. Go to Cloudflare's DNS for `magneticanomaly.llc`, delete the GoDaddy MX records, and paste the Thundermail MX records. 
5. *You are done.* You do not need to touch the forwarding settings for any of the other 5 apps, because they are already forwarding to the Mothership!
