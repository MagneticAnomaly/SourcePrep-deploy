# Emerging & Specialized Tools Research

> Tools that are newer, cloud-based, or specialized -- tracking for future Prep integration.

**Status:** PRELIMINARY
**Last updated:** 2026-03-14

---

## 1. Google Jules

| Property | Value |
|----------|-------|
| **Type** | Asynchronous cloud coding agent |
| **Vendor** | Google |
| **Model** | Gemini 2.5 |
| **MCP Support** | API-based. MCP via wrapper (not native client). |
| **Rules File** | `AGENTS.md` (confirmed on agents.md site) |
| **Status** | Public (out of beta) |

### How Jules Works
- Jules runs asynchronously in Google's cloud
- Triggered from GitHub Issues, PRs, or API calls
- Creates branches, makes changes, runs tests, pushes PRs
- Does NOT run locally -- no direct access to local Prep daemon

### Prep Integration Strategy
- **Primary**: `AGENTS.md` with atlas -- Jules reads this from the repo for structural awareness
- **Future**: MCP server wrapper around Jules API could allow Prep to be called remotely
- **Static context**: Same as Copilot coding agent -- atlas in AGENTS.md provides offline structural context

### Key Consideration
Jules runs in a cloud sandbox. Prep's local daemon is inaccessible. The atlas in AGENTS.md is the ONLY mechanism for structural context delivery to Jules. This makes the quality and completeness of the atlas critical.

---

## 2. OpenAI Codex

| Property | Value |
|----------|-------|
| **Type** | CLI agent (terminal-based) |
| **Vendor** | OpenAI |
| **Model** | GPT-4o, o3, o4-mini (configurable) |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` + `AGENTS.override.md` |
| **Status** | Public |

### AGENTS.md Handling
Codex has the most sophisticated AGENTS.md handling:
- Walks from project root down to current working directory
- Checks for `AGENTS.override.md` first, then `AGENTS.md`, then fallback names
- Supports directory-scoped instructions

### Prep Integration
- **Primary**: AGENTS.md section with atlas (read automatically)
- **Secondary**: MCP tools via standard configuration
- Codex's directory-walking behavior means Prep could generate scoped AGENTS.md files for different project modules (advanced future feature)

---

## 3. Devin (Cognition)

| Property | Value |
|----------|-------|
| **Type** | Cloud autonomous coding agent |
| **Vendor** | Cognition (also owns Windsurf now) |
| **Model** | Proprietary |
| **MCP Support** | Partial (evolving) |
| **Rules File** | `AGENTS.md` (confirmed) |
| **Status** | Public |

### Prep Integration
- Devin runs in cloud sandbox -- same constraint as Jules
- AGENTS.md is the primary mechanism
- Cognition's acquisition of Windsurf/Codeium may lead to shared MCP infrastructure

---

## 4. Junie (JetBrains)

| Property | Value |
|----------|-------|
| **Type** | JetBrains IDE agent |
| **Vendor** | JetBrains |
| **Model** | Claude, GPT (configurable) |
| **MCP Support** | YES |
| **Rules File** | `.junie/guidelines.md` + `AGENTS.md` |
| **Status** | Public |

### Prep Integration
- **Primary**: AGENTS.md (universal)
- **Secondary**: `.junie/guidelines.md` (Junie-specific)
- Junie-specific guidelines could include Prep instructions
- Interesting because it expands Prep beyond VS Code ecosystem into IntelliJ/PyCharm/WebStorm

### Prep Template for `.junie/guidelines.md`
```markdown
## Prep Integration

This project uses Prep for structural code intelligence via MCP.
Call `prep` at the start of every task for module structure and hub files.
Use `prep_search` for code queries. Use `prep_impact` before changes.
```

---

## 5. Kilo Code

| Property | Value |
|----------|-------|
| **Type** | VS Code extension |
| **Vendor** | Kilo Code |
| **Model** | Any (user-configurable) |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` |
| **Status** | Public |

### Prep Integration
- AGENTS.md is the primary mechanism
- Similar architecture to Cline/Roo Code (VS Code extension with agentic loop)
- No special Prep consideration beyond standard AGENTS.md + MCP

---

## 6. OpenHands (formerly OpenDevin)

| Property | Value |
|----------|-------|
| **Type** | Cloud agent platform (open source) |
| **Vendor** | All Hands AI |
| **Model** | Any (Claude, GPT, etc.) |
| **MCP Support** | Partial (evolving) |
| **Rules File** | Custom configuration |
| **Status** | Public, 65K+ GitHub stars |

### Architecture
- Runs agents in Docker containers
- Web-based UI
- Devin-like experience but open source
- Primarily cloud/container-based

### Prep Integration
- OpenHands runs in containers -- Prep daemon would need to run alongside or be accessible via HTTP
- MCP support is evolving -- monitor for full MCP client support
- Static context via AGENTS.md is the safest near-term approach

---

## 7. Goose (Block)

| Property | Value |
|----------|-------|
| **Type** | CLI agent |
| **Vendor** | Block (formerly Square) |
| **Model** | Any |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` |
| **Status** | Public, open source |

### Prep Integration
Standard AGENTS.md + MCP pattern. No special considerations.

---

## 8. Warp

| Property | Value |
|----------|-------|
| **Type** | AI-native terminal |
| **Vendor** | Warp |
| **Model** | Various |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` + Warp rules |
| **Status** | Public |

### Prep Integration
Warp is a terminal replacement with AI features. Prep could be used via:
- MCP tools in Warp's AI chat
- AGENTS.md for project context
- Terminal commands (`prep search ...`) as a fallback

---

## 9. Augment Code

| Property | Value |
|----------|-------|
| **Type** | CLI agent |
| **Vendor** | Augment Code |
| **Model** | Various |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` |
| **Status** | Public |

### Prep Integration
Standard AGENTS.md + MCP pattern.

---

## 10. Factory.ai

| Property | Value |
|----------|-------|
| **Type** | Enterprise AI agent platform |
| **Vendor** | Factory.ai |
| **Model** | Various |
| **MCP Support** | Full MCP |
| **Rules File** | `AGENTS.md` |
| **Status** | Enterprise |

### Prep Integration
- Factory has its own "Droids" (specialized agents)
- AGENTS.md is the primary instruction file
- Enterprise deployments may need Prep's HTTP transport (not just stdio)

---

## Summary: Priority Tracking

### Track Closely (high user demand expected)
1. **OpenAI Codex** -- major player, full MCP, AGENTS.md
2. **Junie (JetBrains)** -- expands beyond VS Code ecosystem
3. **Kilo Code** -- growing VS Code extension

### Monitor (cloud agents, limited integration)
4. **Google Jules** -- AGENTS.md only (cloud sandbox)
5. **Devin** -- Cognition/Windsurf synergy
6. **OpenHands** -- large community, evolving MCP

### Low Priority (niche or well-served by AGENTS.md)
7. **Goose** -- standard AGENTS.md + MCP
8. **Warp** -- terminal focus, standard MCP
9. **Augment Code** -- standard AGENTS.md + MCP
10. **Factory.ai** -- enterprise, standard AGENTS.md
