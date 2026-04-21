# Continue.dev Integration Research

> How Continue consumes MCP, its open-source model-agnostic architecture, and Prep optimization.

**Status:** PRELIMINARY -- needs empirical validation
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | VS Code / JetBrains extension (open source) |
| **Vendor** | Continue.dev (open source, Apache 2.0) |
| **Model** | Any (local or cloud -- fully configurable) |
| **MCP Spec** | Full (tools, resources) |
| **Transport** | stdio, SSE, Docker containers |
| **Rules File** | `config.yaml` rules section |
| **AGENTS.md** | Not confirmed (uses its own config.yaml format) |
| **Unique Feature** | "Continue Hub" for sharing MCP configurations |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support. Continue's agent can call MCP tools.
- **Resources**: Supported. Can be used as context providers.
- **Prompts**: Not documented as MCP prompts, but Continue has its own prompt system.

### Configuration
Continue uses `config.yaml` for all configuration, including MCP:

```yaml
# .continue/config.yaml
mcpServers:
  - name: prep
    command: prep
    args: ["mcp"]
```

### Docker Integration
Continue has partnered with Docker for containerized MCP servers. Prep could potentially be distributed as a Docker MCP container for easier setup.

### Context Providers
Continue has a unique "context provider" abstraction that sits alongside MCP:
- `@file` -- file content
- `@codebase` -- codebase search
- `@docs` -- documentation
- Custom context providers via plugins

Prep could also be implemented as a **Continue context provider** in addition to an MCP server. This would make Prep's context available via `@prep` in Continue's chat.

---

## 3. Rules File: `config.yaml`

### Format
Continue uses YAML configuration with a `rules` section:

```yaml
# .continue/config.yaml
rules:
  - name: Prep Integration
    rule: |
      This project uses Prep for structural code intelligence via MCP.
      ALWAYS call `prep` at the start of every task.
      Use `prep_search` for code queries.
      Use `prep_impact` before changes.
```

### Prep Strategy
1. **Primary**: Generate `AGENTS.md` section (if Continue adds support)
2. **Secondary**: Document how to add Prep rules to `config.yaml`
3. **Future**: Build a Continue context provider for `@prep`

---

## 4. Special Considerations

### Continue Hub
Continue Hub is a sharing platform for MCP configurations. Publishing Prep's MCP config to Continue Hub would make it one-click installable for Continue users.

### Local LLM Focus
Continue is popular among local LLM users (Ollama, LM Studio, llama.cpp). Same implications as Cline/Roo Code -- compact context, clear tool descriptions.

### JetBrains Support
Continue works in JetBrains IDEs (IntelliJ, PyCharm, etc.), expanding Prep's reach beyond VS Code.

---

## 5. Prep Optimization Checklist

- [ ] Test Prep MCP integration in Continue
- [ ] Document config.yaml setup for Prep
- [ ] Explore Continue context provider API for `@prep`
- [ ] Publish Prep config to Continue Hub
- [ ] Test with local LLMs via Continue
- [ ] Verify JetBrains integration works with MCP

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Continue's config.yaml format differs from all others | MEDIUM | Can't auto-generate. Must document. |
| No AGENTS.md support | LOW | Continue may add it. config.yaml rules work meanwhile. |
| Context provider vs. MCP tool confusion | LOW | Both can coexist. |
