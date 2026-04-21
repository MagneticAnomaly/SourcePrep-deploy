# Phase 12 — Open Questions

Decisions needed before the marketing site can ship. Each section includes context and a recommendation.

---

## 1. Blog Platform

**Question:** Where do blog posts live?

**Options:**
| Option | Pros | Cons |
|---|---|---|
| **MDX in marketing site** (recommended) | Full SEO ownership at runprep.io/blog, zero extra cost, version-controlled posts, same design system | Need to add `@next/mdx` or `contentlayer` to the marketing app |
| **Medium** | Easy to start, built-in audience | Lose SEO, no custom domain (without paid partnership), looks less professional for dev tools |
| **Ghost (hosted)** | Own your content, newsletters built in, custom domain | Monthly cost ($9–31/mo), separate system to maintain |
| **Hashnode** | Custom domain, developer audience, free | Less control over design, another platform to manage |

**Recommendation:** MDX in the marketing site + cross-post to **Dev.to** and **Hashnode** (both support canonical URLs back to runprep.io so you keep SEO value). This is what most successful dev tools do (Vercel, Supabase, Linear).

**Action needed:** Decide yes/no on MDX. If yes, add `@next/mdx` to the marketing app.

---

## 2. Community Strategy

**Question:** Where does the community live?

**Options:**
| Option | Pros | Cons |
|---|---|---|
| **GitHub Discussions** (recommended to start) | Free, developer-native, searchable, tied to repo, low moderation burden | Less real-time, less "social" feel |
| **Discord** | Real-time chat, popular for dev tools, good for engagement | Requires active moderation, content isn't searchable by Google, time sink |
| **Discourse (hosted)** | Forum-style, async, great for searchable knowledge | $50+/mo hosted, heavyweight for early stage |

**Recommendation:** Start with **GitHub Discussions** (zero cost, developer-native, good for pre-launch). Add **Discord** later when you have 50+ active users who want real-time chat. Don't bother with Discourse until much bigger.

**Action needed:** Enable GitHub Discussions on the repo. Update /community page link once live.

---

## 3. Social Accounts

**Question:** Which social accounts should exist at launch?

| Platform | Priority | Notes |
|---|---|---|
| **GitHub** | Must-have | Already exists |
| **Twitter/X** | Must-have | @prep or @prep_io — needed for developer credibility |
| **LinkedIn** | Nice-to-have | Company page, useful for enterprise credibility |
| **Dev.to** | Nice-to-have | Cross-post blog content |
| **YouTube** | Later | Demo videos, tutorials — high effort, high reward |

**Action needed:** Create Twitter/X account. Update SiteFooter socials prop with real URLs.

---

## 4. Legal Review

**Question:** Do the Privacy Policy and Terms of Service need legal review before launch?

**Context:** The current drafts are reasonable templates based on standard SaaS/desktop software terms. They accurately reflect Prep's local-first architecture and Lemon Squeezy payment processing.

**Recommendation:** Have a lawyer review both before public launch. Budget ~$500–1500 for a startup-focused tech lawyer to review and redline. Services like Clerky or a solo tech attorney can do this quickly.

**Action needed:** Decide timeline — is this blocking v1.0 launch?

---

## 5. Company Entity

**Question:** Is "Prep Inc." the correct legal entity name?

**Context:** The Terms and Privacy Policy reference "Prep Inc." — this should match whatever entity is (or will be) registered and used for Lemon Squeezy merchant of record setup.

**Action needed:** Confirm entity name or update placeholder.

---

## 6. Careers — Real or Placeholder?

**Question:** Should the careers page show real open positions or stay as aspirational placeholders?

**Current state:** Three template positions (Rust Engineer, Full-Stack Engineer, Developer Advocate) with `careers@runprep.io` as the apply link.

**Recommendation:** Keep as-is for launch — it signals ambition and professionalism. Remove or update if you start getting actual applicants you can't respond to. Consider adding "We're not actively hiring yet, but..." disclaimer if desired.

**Action needed:** Decide if any disclaimer is needed.

---

## 7. Changelog — Data Source

**Question:** Should changelog entries be hardcoded or pulled from a data source?

**Options:**
- **Hardcoded in page** (current) — simple, works now
- **JSON/MDX files** — version-controlled, easy to add entries
- **GitHub Releases API** — auto-populate from release notes

**Recommendation:** Move to MDX or JSON files once there are 5+ entries. Current hardcoded approach is fine for launch.

**Action needed:** None for now.

---

## 8. Domain & DNS

**Question:** Are all subdomains configured?

| Domain | Purpose | Status |
|---|---|---|
| `runprep.io` | Marketing site | ? |
| `docs.runprep.io` | Documentation | ? |
| `payments.runprep.io` | Payment / licensing portal | ? |
| `api.runprep.io` | License activation API | ? |
| `blog.runprep.io` | Blog (only if not using /blog path) | Not needed if MDX |

**Action needed:** Verify DNS records exist for all required subdomains.

---

## 9. Analytics

**Question:** Should the marketing site have analytics?

**Recommendation:** Use a privacy-respecting, cookie-free option:
- **Plausible** ($9/mo) — EU-hosted, no cookies, GDPR-compliant
- **Fathom** ($14/mo) — similar
- **Umami** (self-hosted, free) — open source

This is referenced in the Privacy Policy as "privacy-respecting analytics (no cookies, no personal data)."

**Action needed:** Pick a provider and add the script to `layout.tsx`.

---

## 10. Email Infrastructure

**Question:** Which email addresses need to work at launch?

| Address | Purpose |
|---|---|
| `hello@runprep.io` | General contact |
| `support@runprep.io` | Support tickets |
| `billing@runprep.io` | Payment/licensing questions |
| `security@runprep.io` | Responsible disclosure |
| `privacy@runprep.io` | Privacy/data requests |
| `careers@runprep.io` | Job applications |
| `legal@runprep.io` | Legal inquiries |

**Recommendation:** Use a catch-all for now (all go to one inbox), then split as volume grows. Google Workspace ($6/user/mo) or Fastmail ($5/user/mo) both work.

**Action needed:** Set up email or confirm catch-all exists.
