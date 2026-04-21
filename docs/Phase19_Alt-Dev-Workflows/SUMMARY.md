# Alternative Dev Workflows: The "Context MVC" Strategy

## Executive Summary
We have shifted our integration strategy from building custom plugins to a **Context MVC (Model-View-Controller)** architecture.

- **Model**: Prep (The "Context Model"). Provides the structural graph and search via **MCP**.
- **View**: External Tools (The "Client"). Handles the UI and LLM interaction.

**Strategic Decision**: We only officially support and verify tools that implement the **Model Context Protocol (MCP)** as a client. We do not build custom adapters for tools that lack MCP support.

## Integration Status Matrix

| Tool | Role | MCP Support | Strategy | Feasibility |
|------|------|-------------|----------|-------------|
| **Gemini CLI Desktop** | **Tier 1 View** | ✅ Native Client | **Verify & Document** | High (1 week) |
| **Qwen Code** | **Tier 1 View** | ✅ Native Client (via Qwen-Agent) | **Verify & Document** | High (2 weeks) |
| **Claude Desktop** | **Tier 1 View** | ✅ Native Client | **Already Supported** | Done |
| **AionUi** | *Out of Scope* | ❌ Requires Adapter | **Deprioritize** | Low (High Effort) |

## Implementation Roadmap

### Phase 1: Verification (Immediate)
1.  **Gemini CLI Desktop**: Test Prep as an MCP server configuration in `settings.json`.
2.  **Qwen Code**: Verify `mcpServers` configuration in Qwen Code's config (based on Qwen-Agent framework).

### Phase 2: Documentation (Marketing)
1.  Create **"Verified Views"** section on the marketing website.
2.  Publish setup guides for Gemini CLI Desktop and Qwen Code.
3.  Position Prep as the "Universal Context Backend" for local AI tools.

## Research Findings

### 1. Gemini CLI Desktop
*   **Verdict**: Perfect fit. It is essentially an open-source alternative to Claude Desktop.
*   **Action**: Create `docs/integrations/gemini-cli.md` guide.

### 2. Qwen Code
*   **Verdict**: Strong fit. Built on Qwen-Agent which natively supports MCP to give agents tools.
*   **Action**: Create `docs/integrations/qwen-code.md` guide.

### 3. AionUi
*   **Verdict**: **Archived**. While powerful, it requires custom API adapters and targets enterprise workflows that are currently out of scope.
*   **Action**: No further work.

## References
- [Unified Strategy Concept](./UNIFIED_STRATEGY.md)
- [Qwen Code Research](./qwen-code.md)
- [Gemini CLI Desktop Research](./gemini-cli-desktop.md)
