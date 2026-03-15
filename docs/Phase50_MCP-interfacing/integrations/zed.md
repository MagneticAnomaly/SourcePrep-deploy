# Zed Integration Research

> How Zed editor consumes MCP, its native AI agent panel, and CoDRAG optimization.

**Status:** PRELIMINARY
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | Native editor (Rust-based, not VS Code) |
| **Vendor** | Zed Industries |
| **Model** | Claude, GPT, Gemini, local (user-configurable) |
| **MCP Spec** | Tools + partial resources |
| **Transport** | stdio |
| **Rules File** | `.rules` files + `AGENTS.md` |
| **AGENTS.md** | YES (confirmed on agents.md site) |
| **Unique Feature** | Agent Panel with "Text Threads" for raw LLM conversation |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support in Agent Panel
- **Resources**: Partial support (model compatibility warnings shown)
- **Prompts**: Not documented

### Tool Permissions
Zed has a granular tool permission system:

```
mcp:<server_name>:<tool_name>
```

Permissions can be set to:
- `always_allow` -- no confirmation needed
- `always_deny` -- tool is blocked
- `always_confirm` -- always ask user

### Model Compatibility
Not all models support all MCP tools. Zed's UI shows a warning icon near the model selector when incompatibility is detected. This is relevant for CoDRAG with local models that may not handle tool-calling well.

### Agent Client Protocol (ACP)
Zed also supports ACP (Agent Client Protocol) for deeper integrations. Qwen Code integrates with Zed via ACP. CoDRAG currently uses MCP only, which works with Zed's Agent Panel.

---

## 3. Rules File: `.rules`

### Format
Zed uses `.rules` files for AI instructions. These can be:
- Project-level (in project root)
- Directory-level (scoped to subdirectories)

### AGENTS.md Support
Zed reads AGENTS.md. The CoDRAG section in AGENTS.md is the primary integration path.

### CoDRAG Strategy
1. **Primary**: AGENTS.md section (universally read)
2. **Optional**: `.rules` file if Zed is detected

---

## 4. Unique Zed Features

### Text Threads
Zed's "Text Threads" present conversations as raw text rather than rich UI. This means CoDRAG's markdown responses are displayed as-is, making clean formatting even more important.

### Performance
Zed is built in Rust and is very fast. MCP tool call latency is more noticeable in Zed's snappy UI. CoDRAG's daemon architecture (pre-built index, fast responses) is a good fit.

### Multi-Model
Zed supports switching models mid-conversation. CoDRAG's tool descriptions must work across all supported models.

---

## 5. CoDRAG Optimization Checklist

- [ ] Test CoDRAG MCP integration in Zed's Agent Panel
- [ ] Verify AGENTS.md reading behavior
- [ ] Test tool permissions: configure `always_allow` for CoDRAG tools
- [ ] Test with Text Threads format (verify markdown rendering)
- [ ] Check model compatibility warnings with CoDRAG tools

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Partial resource support | LOW | CoDRAG works primarily via tools. Resources are supplementary. |
| Model compatibility warnings scare users | LOW | CoDRAG tools use simple schemas. Most models handle them. |
| Zed's smaller market share | LOW | Growing fast. Early CoDRAG support is strategic. |
