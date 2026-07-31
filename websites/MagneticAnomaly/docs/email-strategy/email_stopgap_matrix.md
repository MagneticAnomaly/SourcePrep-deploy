# Portfolio Email Stopgap Matrix

This matrix documents the interim "stopgap" strategy for all domains and email addresses across the portfolio. Use this as your master checklist for what to set up right now, and as your migration map when Thundermail is ready.

| App / Project | Domain | Current DNS Host | Stopgap Email Strategy | Email Addresses Needed | Future Migration to Thundermail |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Magnetic Anomaly** | `magneticanomaly.llc` | GoDaddy | **Keep cPanel** | `hello@` or `contact@` | 1. Move DNS to Cloudflare<br>2. Migrate data via Thunderbird<br>3. Change MX to Thundermail |
| **HomeColab** | `homecolab.app` | GoDaddy | **Keep cPanel** | `support@`, `privacy@` | 1. Move DNS to Cloudflare<br>2. Migrate data via Thunderbird<br>3. Change MX to Thundermail |
| **SourcePrep** | `sourceprep.io` | Cloudflare | **Cloudflare Forwarding** | `support@`, `enterprise@`, `licenses@`, `security@`, `bugs@` | 1. Turn off Forwarding<br>2. Change MX to Thundermail |
| **Applivation** | `applivation.app` | Cloudflare | **Cloudflare Forwarding** | `support@` | 1. Turn off Forwarding<br>2. Change MX to Thundermail |
| **DinnerVision** | `dinnervision.app` | None (Unconfigured) | **Set up in GoDaddy cPanel** | `support@` | 1. Move DNS to Cloudflare<br>2. Migrate data via Thunderbird<br>3. Change MX to Thundermail |
| **DebateHaus** | `debatehaus.app` | None (Unconfigured) | **Set up in GoDaddy cPanel** | `beta@` or `hello@` | 1. Move DNS to Cloudflare<br>2. Migrate data via Thunderbird<br>3. Change MX to Thundermail |

---

### Stopgap Action Items (To do right now)

1. **For the Cloudflare domains (`sourceprep.io`, `applivation.app`):** 
   * Log into Cloudflare, go to Email Routing, and set up forwarding rules for the 6 addresses listed above so they deliver to your personal inbox.
2. **For the Unconfigured domains (`dinnervision.app`, `debatehaus.app`):** 
   * Log into GoDaddy and ensure the domains are pointing to GoDaddy's default nameservers.
   * Go into your cPanel and create the 2 inboxes for these domains so they are ready to receive mail. Add them to Thunderbird.
3. **For the GoDaddy domains (`magneticanomaly.llc`, `homecolab.app`):** 
   * Do nothing. Leave them exactly as they are in cPanel/Thunderbird. 

*When the time comes to migrate to Thundermail, you will only have to deal with migrating historical data for the GoDaddy/cPanel accounts. The Cloudflare forwarding accounts will have zero data to migrate, making the switch instantaneous.*
