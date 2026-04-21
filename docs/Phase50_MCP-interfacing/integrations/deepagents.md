# DeepAgents (LangChain) Integration Research

> How DeepAgents consumes MCP via langchain-mcp-adapters, its agent harness architecture, and Prep optimization.

**Status:** PRELIMINARY
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | Python agent harness (CLI, terminal-based) |
| **Vendor** | LangChain |
| **Model** | Any (via LangChain providers -- OpenAI, Anthropic, Google, Ollama, etc.) |
| **MCP Spec** | Via `langchain-mcp-adapters` library |
| **Transport** | stdio (via adapter) |
| **Rules File** | N/A (programmatic configuration) |
| **AGENTS.md** | NO (not a file-reading tool -- instructions are in code) |
| **Open Source** | YES (github.com/langchain-ai/deepagents) |
| **Architecture** | LangGraph state machine with planning, sub-agents, context management |

---

## 2. How DeepAgents Differs from Other Tools

DeepAgents is NOT an IDE or a standalone coding assistant. It is an **agent framework harness** that:
- Orchestrates LLM agents using LangGraph (state machine)
- Provides planning capability (decompose tasks into subtasks)
- Spawns sub-agents for parallel work
- Has file access, shell access, and context management
- Uses MCP via the `langchain-mcp-adapters` library

### Key Distinction
Where Cursor/Claude Code/Gemini CLI are **end-user products**, DeepAgents is a **building block**. Developers use it to create custom coding agents. Prep integration here means making Prep available as an MCP tool to any LangGraph-based agent.

---

## 3. MCP Implementation via langchain-mcp-adapters

### How It Works
The `langchain-mcp-adapters` library bridges MCP servers into LangChain's tool abstraction:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient(
    {
        "prep": {
            "command": "prep",
            "args": ["mcp"],
            "transport": "stdio",
        }
    }
) as client:
    tools = client.get_tools()
    # tools now contains LangChain Tool objects for each Prep MCP tool
    # These can be passed to any LangChain agent
```

### What Gets Exposed
- MCP tools become LangChain `Tool` objects with:
  - `name`: the MCP tool name
  - `description`: the MCP tool description
  - `args_schema`: derived from MCP inputSchema
- Tool invocation goes through the MCP client, which handles stdio transport

### What Gets Lost
- **MCP Resources**: Not supported by langchain-mcp-adapters (tools only)
- **MCP Prompts**: Not supported
- **MCP Instructions**: Not supported (no initialize instructions field)
- **Rules files**: DeepAgents doesn't read AGENTS.md or any convention files

### Implications for Prep
Without resources, prompts, or instructions, Prep's **tool descriptions** are the ONLY mechanism to guide DeepAgents' behavior. The descriptions must be self-contained:

```
prep: "Get ambient codebase context -- structural overview, module map, hub files,
and user-selected focus areas. Call this FIRST at the start of every coding task to
understand the codebase architecture before making changes."
```

---

## 4. Context Architecture

### LangGraph State Machine
DeepAgents uses a LangGraph state machine with these key states:
- **Planning**: decompose user request into subtasks
- **Executing**: run subtasks (may involve tool calls)
- **Reviewing**: verify results
- **Iterating**: fix issues and retry

### Sub-Agent Context
Each sub-agent has its own context window. Prep's compact ambient response (~250 tokens) is ideal because:
- Sub-agents need structural context but can't afford large payloads
- The main agent can call `prep` once and inject the result into sub-agent prompts
- Sub-agents can then call `prep_search` for specific queries

### Context Management
DeepAgents has its own context management (summarization, window management). Prep's tool responses are subject to this -- early responses may be summarized in long tasks.

---

## 5. Programmatic Integration Pattern

Since DeepAgents is code-first, Prep integration is via code, not config files:

```python
# Example: DeepAgents with Prep
from deepagents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    async with MultiServerMCPClient({
        "prep": {
            "command": "prep",
            "args": ["mcp"],
            "transport": "stdio",
        }
    }) as mcp_client:
        prep_tools = mcp_client.get_tools()
        
        agent = create_agent(
            model="claude-sonnet-4-20250514",
            tools=[*built_in_tools, *prep_tools],
            system_prompt="""You have access to Prep structural code intelligence.
            ALWAYS call prep first for module structure and hub files.""",
        )
        
        result = await agent.invoke("Fix the authentication bug")
```

### Key Point: System Prompt is Developer-Controlled
Unlike IDE tools where Prep generates rules files, DeepAgents' system prompt is controlled by the developer building the agent. Prep's documentation should include a **recommended system prompt snippet** for LangChain/DeepAgents users.

---

## 6. Prep Documentation for DeepAgents Users

### Recommended System Prompt Addition
```
You have access to Prep, a structural code intelligence system that understands
this codebase through a trace graph of imports, calls, and relationships.

ALWAYS call `prep` (no arguments) at the START of every task. This gives you:
- Module structure (groups of files and their dependencies)
- Hub files (most connected files with full content)
- User's focus areas

For specific code lookups, use `prep_search` with a natural language query.
Before making changes, use `prep_impact` to understand dependencies.
```

### Recommended Tool Configuration
```python
mcp_config = {
    "prep": {
        "command": "prep",
        "args": ["mcp"],
        "transport": "stdio",
        "env": {
            "PREP_PROJECT": "/path/to/project"  # optional: explicit project
        }
    }
}
```

---

## 7. Prep Optimization Checklist

- [ ] Test Prep MCP tools via langchain-mcp-adapters
- [ ] Verify all 5 Prep tools convert correctly to LangChain Tool objects
- [ ] Test with multiple LLM providers (OpenAI, Anthropic, Google) via LangChain
- [ ] Create example integration script for DeepAgents + Prep
- [ ] Document recommended system prompt snippet
- [ ] Test sub-agent context injection with Prep ambient response
- [ ] Verify tool schema compatibility after LangChain conversion

---

## 8. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| langchain-mcp-adapters drops resources/prompts/instructions | HIGH | Tool descriptions must be self-contained. All guidance in descriptions. |
| LangChain tool schema conversion loses detail | MEDIUM | Test that all Prep parameters survive conversion. |
| Developer must manually add system prompt | MEDIUM | Document clearly. Can't auto-generate for programmatic tools. |
| Sub-agent context too small for Prep responses | LOW | 250-token ambient response fits any context window. |
| DeepAgents is newer/less stable than IDE tools | MEDIUM | Monitor for breaking changes. LangChain ecosystem evolves fast. |
