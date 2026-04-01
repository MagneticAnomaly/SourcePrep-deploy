# Role-Aware Context Delivery

CoDRAG shapes each context delivery around the role of the agent (or person) asking — so every worker gets a focused, high-signal view without wading through irrelevant code.

A security reviewer sees authentication and data boundaries. A UI agent sees components and design tokens. A CEO sees module summaries and strategic health. Same codebase index — no extra setup required.

---

## Quick Start

### Via MCP (Cursor, Windsurf, Claude Desktop, Antigravity)

Any MCP-connected agent can pass the `role` parameter:

```
codrag(role="security")
codrag(role="design engineer")
codrag(role="ceo")
codrag(role="QADevOpsLead")
```

The agent receives the standard codebase atlas, filtered and weighted for that role's perspective.

### Via CLI

```bash
# Get context filtered for a specific role
codrag context --role "frontend engineer"
codrag context --role "cto"
codrag context --role "intern"
```

### Via API

```
GET /projects/{project_id}/atlas?role=security
GET /projects/{project_id}/atlas?role=design+engineer
```

Returns the standard atlas response with an additional `role_atlas` field containing the role-filtered view.

---

## How It Works

CoDRAG's epistemic enrichment pipeline already classifies every file along multiple dimensions:

| Dimension | Source | Example Values |
|-----------|--------|---------------|
| Architecture Layer | Enrichment Pass 2 | `presentation`, `business_logic`, `infrastructure`, `testing` |
| Domain Tags | Enrichment Pass 2 | `auth`, `ui`, `data-persistence`, `api` |
| Graph Centrality | Trace Edges | In-degree count (hub files score higher) |
| Epistemic Confidence | 6-component score | 0.0–1.0 understanding score |

**A role is a weight vector across these dimensions.** Instead of building separate indexes per role, CoDRAG applies a lens over the existing index:

```
"Security Engineer" → emphasize infrastructure, configuration, data layers
                    → boost files tagged auth, token, encryption, permission
                    → prefer hub files (high centrality)
                    → practitioner detail level (show code-level context)

"CEO"               → emphasize documentation, business_logic layers
                    → boost files tagged strategy, architecture, monetization
                    → strongly prefer hub files (most-connected things)
                    → executive detail level (module summaries only)
```

**Zero additional pipeline cost.** Role projection is pure Python filtering on cached data — typically <1ms from the pre-generated cache, ~200ms for live generation of novel compound roles.

---

## Supported Roles

CoDRAG resolves any free-form role string. Here is how it maps titles across departments:

### Executive & Leadership

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| CEO, President, Founder, Board Member | Executive overview | Summary |
| CTO, VP of Engineering, CIO | Technical leadership | Manager |
| CFO, COO, Controller, Treasurer | Executive overview | Summary |
| CISO | Security leadership | Manager |
| CPO, VP of Product | Product leadership | Manager |
| Managing Director, Partner | Executive overview | Summary |

### Engineering

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Software Engineer, Backend Developer | Engineering (full) | Practitioner |
| Frontend Developer, Full Stack Developer | Full-stack (UI emphasis) | Practitioner |
| Mobile/iOS/Android Developer | Full-stack (UI emphasis) | Practitioner |
| Senior/Staff/Principal Engineer | Engineering (less detail, more strategic) | Manager |
| Junior Developer, Intern | Engineering (more detail, more docs) | Practitioner+ |

### Design & Creative

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| UX Designer, UI Designer, Visual Designer | Design (presentation-heavy) | Practitioner |
| Art Director, Creative Director | Design (presentation-heavy) | Manager |
| Product Designer | Product + Design blend | Practitioner |
| Motion Designer, Brand Designer | Design (presentation-heavy) | Practitioner |
| UX Researcher, Design Manager | Design (presentation-heavy) | Manager |

### Security

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Security Engineer, Application Security | Security (infra + config focus) | Practitioner |
| Penetration Tester, SOC Analyst | Security (infra + config focus) | Practitioner |
| Compliance Officer, Security Auditor | Security (compliance emphasis) | Manager |
| Threat Intelligence Analyst | Security (infra + config focus) | Practitioner |

### DevOps & Infrastructure

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| DevOps Engineer, SRE | DevOps (infra + build focus) | Practitioner |
| Cloud Architect | DevOps + Architecture blend | Manager |
| Database Administrator, Systems Admin | DevOps (infra focus) | Practitioner |
| Infrastructure/Network/Release Engineer | DevOps (infra focus) | Practitioner |

### Product & Project

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Product Manager, Product Owner | Product (business logic focus) | Manager |
| Program Manager, Project Manager | Product (business logic focus) | Manager |
| Scrum Master | Product (business logic focus) | Manager |
| Business Analyst, Product Analyst | Product (data + business focus) | Manager |

### Data / AI / ML

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Data Scientist, Data Engineer | Data (data layer focus) | Practitioner |
| ML Engineer, NLP Engineer | Data (infra + data focus) | Practitioner |
| BI Analyst, Data Analyst | Data (data layer focus) | Manager |

### Marketing / Content

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Marketing Manager, CMO | Writer (docs + content focus) | Manager |
| Content Writer, Technical Writer | Writer (docs focus) | Practitioner |
| SEO Specialist, Social Media Manager | Writer (content focus) | Manager |
| Copywriter, Content Strategist | Writer + Product blend | Manager |

### Sales & Business Development

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Sales Manager, Account Executive | Product (business focus) | Manager |
| Customer Success Manager | Product (user-facing focus) | Manager |
| Solutions Consultant | Architect (solutions focus) | Manager |

### Finance / Legal / HR

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Accountant, Financial Analyst | Executive (finance view) | Summary |
| General Counsel, Corporate Attorney | Security (compliance view) | Manager |
| HR Manager, Recruiter, Head of Talent | Product (people ops view) | Manager |

### Support & DevRel

| Title | Resolved As | Detail Level |
|-------|------------|:---:|
| Technical Support Engineer | QA (user-facing view) | Practitioner |
| Developer Advocate | Writer (content view) | Practitioner |
| Community Manager | Writer (content view) | Manager |

---

## Compound Roles

CoDRAG decomposes compound role names automatically via keyword blending:

```
"Design Engineer"       → blend(design=50%, engineering=50%)
"DevSecOps"             → blend(devops=33%, security=33%, engineering=33%)
"Senior QA Lead"        → qa base + senior modifier + lead modifier
"Junior React Developer"→ engineering base + junior modifier (more docs, bigger budget)
```

### CamelCase & Framework Names

Agent framework naming conventions are supported natively:

```
"QADevOpsLead"   → split → "qa dev ops lead" → blend(qa + devops) + lead modifier
"VPContent"      → split → "vp content"      → blend(cto + writer)
"UXDesigner"     → split → "ux designer"      → design
"ContentStrategist" → split → "content strategist" → blend(writer + product)
```

### Modifiers

| Modifier | Effect |
|----------|--------|
| senior, staff, principal | Less detail, more strategic, higher centrality |
| junior, intern | More detail, more docs, bigger context budget |
| lead, head, manager, director | Higher centrality, testing visibility |

---

## Fallback Behavior

If a role string contains no recognizable keywords (e.g., `"Bob"` or `"assistant"`), it falls back to the **engineering** vector — the broadest, most complete view. No agent ever gets empty context.

---

## Caching

Role sub-atlases are pre-cached at two pipeline stages:

1. **Fast Path (Stage 1):** Structural-only role atlases cached using file path heuristics
2. **Deep Enrichment (Stage 9):** Full epistemic role atlases cached using enrichment data

Cache reads are ~0.1ms. Cache is automatically invalidated when the codebase index changes.

Pre-cached roles: `ceo`, `cto`, `engineering`, `design`, `security`, `qa`, `devops`, `product`, `data_engineer`, `architect`, `full_stack`, `writer`, `intern`.

Novel or compound roles (e.g., `"design engineer"`) are computed live in ~200ms and not cached.

---

## Related Documentation

- [MCP Onboarding](./MCP_ONBOARDING.md) — Setting up CoDRAG with AI editors
- [Agentic Integration Guide](./AGENTIC_INTEGRATION_GUIDE.md) — Using CoDRAG with Paperclip, CrewAI, and multi-agent frameworks
- [CLI Reference](./CLI.md) — Full CLI documentation
- [API Reference](./API.md) — HTTP API documentation
