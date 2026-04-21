# Phase 19: Alternative Development Workflows (Context MVC)

## Objective
Shift from building custom plugins to a "Context MVC" architecture where Prep acts as the Model (MCP Server) and external tools act as the View. Verify and document "Verified Views" for Gemini CLI Desktop and Qwen Code.

## Strategy
- **Context MVC**: Prep = Model, Tool = View.
- **Protocol**: MCP (Model Context Protocol).
- **Tier 1 (Verified)**: Native MCP support, local-first.

## Roadmap

### Research (Complete)
- [x] Research Gemini CLI Desktop feasibility (gemini-cli-desktop.md)
- [x] Research Qwen Code feasibility (qwen-code.md)
- [x] Define "Context MVC" unified strategy (UNIFIED_STRATEGY.md)

### Verification (Sprint S-12)
- [ ] **Gemini CLI Desktop**: Test Prep MCP server integration
  - [ ] Install Gemini CLI Desktop
  - [ ] Configure `prep` as MCP server
  - [ ] Verify context fetching
- [ ] **Qwen Code**: Test Prep MCP integration
  - [ ] Verify Qwen-Agent MCP client capabilities
  - [ ] Test with `prep` daemon

### Documentation (Sprint S-12)
- [ ] Create `docs/integrations/gemini-cli.md` guide
- [ ] Create `docs/integrations/qwen-code.md` guide
- [ ] Update Marketing Website "Integrations" page with "Verified Views" section
