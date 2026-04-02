# Animated Component Strategy & Placement Plan

We have our powerful rendering modules (`AnimatedCLI` for quick terminal interactions and `AnimatedIDE` for deep, agentic code-editing workflows). The goal is to maximize their impact on both the **Marketing** site and the **Documentation** site by placing them strategically to prove CoDRAG's value. 

All code examples in these animations will use universally familiar patterns (e.g., e-commerce, simple auth, Stripe billing) so that the core benefit—*context precision*—is immediately obvious to any developer.

Below is the expanded list of placements with 6 variations each.

## User Review Required

> [!NOTE]
> Please review the locations and their 6 variations below. Let me know which 3-4 variations stand out to you as the most powerful. We will then cull the list, write the actual demo data payloads, and embed the components.

---

## 1. Marketing Homepage: Just Below The Hero (`/`)

**Goal:** The immediate hook. Needs to instantly show that CoDRAG acts as the "brain" for the user's AI coding tools. This is the first thing they see when they scroll.

### Variations (IDE Simulator):
1. **The Fast Auth Refactor:** Show an agent using `codrag_search` to find `JWT_SECRET_KEY` usage, then opening `authController.ts` and refactoring how expired tokens are handled instantly.
2. **The Breaking Change Save:** A developer asks the agent to modify a `User` database schema. CoDRAG intercepts via `codrag_impact`, warning the agent that `billing/checkout.ts` and `email/receipts.ts` will break. The agent then adjusts its approach securely.
3. **The Circular Dependency Fix:** The agent runs `codrag_audit`, detects a circular dependency between `Cart` and `Product` modules in an e-commerce app, opens both files side-by-side, and extracts a shared interface.
4. **The UI Component Library Update:** The agent wants to update a Button design system. CoDRAG traces all 40 button usages. The IDE side panel shows the agent updating the core `Button.tsx` and verifying no cascading layout breaks occur.
5. **Onboarding to a Massive Monorepo:** Someone types "Explain the checkout flow". CoDRAG retrieves the 3 hub files for payments. The IDE sidebar prints a pristine summary of the Stripe integration before writing any new code.
6. **The E-Commerce Tax Bug:** The agent is asked to fix a "tax calculation bug". It uses `codrag_search` for "tax rate", finds the exact utility function, opens `TaxCalculator.ts`, and adds a missing edge case for international shipping.

## 2. Marketing: "Compare vs Cloud" Page (`/compare/codrag-vs-greptile`)

**Goal:** Emphasize *Local vs Cloud* architectural differences, speed, and privacy.

### Variations (CLI Terminal):
1. **The Air-Gapped Secret:** Simulate a user asking to search for AWS keys. The Cloud simulation fails. The CoDRAG CLI succeeds instantly because the code never leaves the laptop.
2. **Sub-100ms Search Speed:** A split time-comparison showing a massive AST structural search completing locally in 40ms vs a loading spinner on a competitor.
3. **The "Offline Mode" Airplane Code:** The CLI visibly shows network disconnected, but `codrag_impact` still perfectly traces the dependencies of a `PaymentGateway` change.
4. **The PII Privacy Shield:** The user asks about `handleCustomerCreditCard()`. The agent retrieves the context entirely locally, displaying a badge asserting no PII logic was synced to an external cloud.
5. **No Upload Limits:** Querying a 10,000-file repository. The CLI instantly utilizes the local rust daemon to find `OrderProcessor` without requiring a multi-hour GitHub ingest pipeline.
6. **Bring Your Own Key (BYOK) Demo:** Show the user swapping the inference model from Claude 3.5 Sonnet to local Ollama Llama-3 in the CLI, highlighting that the context engine itself is free and decoupled from the LLM.

## 3. Marketing: ROI / FAQ Page (`/faq` or `/pricing`)

**Goal:** Provide visual, concrete proof for pricing or capability objections.

### Variations (CLI Terminal):
1. **Token Cost Visualization:** Q: "Does this use my whole context window?" The CLI answers a prompt about `AuthenticationContext`, and a bright green meter shows: `Returned 1,200 tokens (1% of context limit)`.
2. **The "Stale Knowledge" Prevention:** Q: "What happens when my code changes?" The user modifies a file. The CLI instantly flags previous AI observations as `[STALE]`, forcing the agent to fetch fresh context for the `InvoiceGenerator`.
3. **Role-Aware Context Savings:** Q: "Can multiple agents use it?" Show a 'Security Agent' querying the same file as a 'UI Agent', but the CLI returns completely different, scoped code chunks for each to save tokens.
4. **Zero-Setup Audit ROI:** Q: "Do I need to train the model?" The CLI runs `codrag_audit` and instantly prints out 5 tech debt tickets (e.g., 'Dead code in notification service'), proving immediate value.
5. **The Enterprise Scale Proof:** Q: "Can it handle my monorepo?" The CLI displays indexing status: `Parsed 2.5 million lines of Python inside 4.2 seconds.`
6. **License Check / Offline Validation:** Demonstrate that the CoDRAG license validation runs locally and does not phone home, highlighting the perpetual software model.

## 4. Documentation: Quick Start Guide

**Goal:** Drive users to their first magical "Aha!" moment with the tool.

### Variations (Mixed):
1. **The Initial Indexing (CLI):** A fast animation showing `npx @codrag/cli init`, tree-sitter parsing an entire NextJS codebase, and displaying "Ready" in seconds.
2. **Your First Question (CLI):** The user types `codrag` with no arguments to get "Ambient Context". The terminal outputs the 2 main hub files for their generic `Dashboard` app.
3. **Starting the MCP Server (CLI):** Show exactly what the console logs look like when the local Rust Daemon spins up on port 3000 and waits for MCP connections.
4. **The Agent Handshake (IDE):** Show an IDE opening and the internal agent acknowledging `CoDRAG MCP Tools Detected. I can now read your codebase structurally.`
5. **Testing a Simple Query (CLI):** Testing the `codrag_search` tool manually on the CLI to find a generic `UserProfile` interface before using it in an AI.
6. **Resolving a Port Conflict (CLI):** A helpful troubleshooting animation showing what happens if the default daemon port is taken and how the CLI auto-resolves it.

## 5. Documentation: IDE & MCP Integrations

**Goal:** Help users visualize integration into Windsurf, Cursor, and Claude Desktop.

### Variations (IDE / Chat Panels):
1. **The Windsurf Cascade (IDE):** An animation styled as Windsurf. The cascade agent is told to "Add a dark mode toggle". It automatically invokes `codrag` to find the `ThemeContext`, then edits the file.
2. **The Cursor Composer (IDE):** Styled as Cursor's multi-file editor. The agent uses `codrag_impact` to find the 3 files dependent on `ThemeConfig`, then opens all 3 and applies the dark mode patch simultaneously.
3. **Claude Desktop Local Interrogation (CLI/Chat):** Themed as the Anthropic Desktop app. The user asks a question about their local `docker-compose.yml`, Claude transparently uses the local MCP server to read it.
4. **VS Code Extension Config (IDE):** Showing the precise JSON edit inside `settings.json` where the user defines the CoDRAG MCP command.
5. **Troubleshooting MCP Connection (CLI):** Showing the "Tools Not Found" error in an agent, followed by the user simply restarting the daemon via CLI to fix the bridge.
6. **Agentic Pipeline (Terminal/Multi-agent):** Show a purely head-less workflow where an automated script uses CoDRAG to review a generic Pull Request and suggest architectural fixes.

## 6. Documentation: The Tools Deep-Dive

**Goal:** Dedicated visual explanations for `codrag`, `codrag_search`, `codrag_impact`, and `codrag_audit`.

### Variations (Mixed):
1. **Structural vs Regex Search (CLI):** `grep "login"` fails due to messy formatting. `codrag_search login` succeeds because it uses AST definition matching, finding both the class and the interface.
2. **Graph Expansion (CLI):** Show `codrag_search` returning the initial file, then the CLI displaying `+ 2 structural neighbors added for context` to explain how it pulls in necessary types.
3. **The Blast Radius Map (IDE):** For `codrag_impact`. The agent is asked to change the `DiscountCode` logic. The IDE side panel visually lists out the 6 files that would break if the schema changes.
4. **Auditing a Legacy File (IDE):** For `codrag_audit`. The agent scans a massive, 2000-line `god-class.ts`. The audit tool flags it as QUAL-1, and the agent begins splitting it into cohesive services.
5. **Project Orientation via `hi_codrag` (CLI):** Specifically demonstrating how `hi_codrag` summarizes graph health (e.g. `98% linked`) and suggests what the developer should focus on next.
6. **The Memory Flag Test (CLI):** Demonstrating the `codrag_observe` tool. The user saves an observation about `DatabaseConfig`. Later, the code changes, and a CLI test command proves the observation was correctly flagged stale.

---
*Awaiting user review on preferred variations to implement.*
