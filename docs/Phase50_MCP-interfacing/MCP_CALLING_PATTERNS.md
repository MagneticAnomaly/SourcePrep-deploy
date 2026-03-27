# MCP Calling Patterns: Prompt Engineering for Natural Tool Invocation

**Last Updated:** 2026-03-26  
**Status:** Active Guide  
**Applies To:** Claude Code, Cursor, Windsurf, and other MCP-enabled AI assistants

---

## The Problem

Current MCP tool calling requires overly explicit prompts. Users shouldn't have to say "Please use the codrag tool to search for..." when simply typing **"codrag"** or **"search the codebase"** should suffice.

### Patterns That DON'T Work Well

| Pattern | Why It Fails | Example |
|---------|--------------|---------|
| **Passive descriptions** | AI treats tool descriptions as informational only | "The codrag tool can search your codebase" |
| **Complex conditional logic** | "If the user asks about X, then call Y" creates decision fatigue | "If the user mentions searching, use codrag_search" |
| **Buried instructions** | Tool calling guidelines hidden in long documents | Instructions at bottom of AGENTS.md |
| **Overly specific triggers** | Requiring exact phrases | "Only call when user says 'activate codrag'" |
| **Narrative announcements** | AI feels need to announce intent | "I will now call the codrag tool..." |

---

## The Simplified Approach

**Core Principle:** The word "codrag" anywhere in user input should be treated as a tool invocation signal.

### What Should Trigger Tool Use

| User Input | Expected AI Behavior |
|------------|-------------------|
| `"codrag"` | Immediately call `codrag()` for ambient context |
| `"use codrag"` | Call `codrag()` without confirmation |
| `"codrag search for..."` | Call `codrag_search(query="...")` |
| `"search the codebase"` | Call `codrag_search()` with the query |
| `"find where X is defined"` | Call `codrag_search()` for X |
| `"what's the structure of..."` | Call `codrag()` for module overview |
| `"how does this project work"` | Call `codrag()` for codebase atlas |

### The "Just-in-Time" Rule

**Don't ask for permission. Don't explain. Just call.**

When you detect intent, make the tool call immediately in the same response. The MCP response will provide context that informs your next reply.

---

## Prompt Engineering Strategies

### 1. Front-Load Tool Instructions

Place tool calling instructions at the **very beginning** of system prompts, not buried in documentation.

**Bad:**
```
## Welcome to CoDRAG
CoDRAG is a code intelligence system...
[500 lines of documentation]
...
When user asks about code, you may use codrag tools.
```

**Good:**
```
CRITICAL: When user mentions "codrag" or code search, IMMEDIATELY call the appropriate tool.

## Welcome to CoDRAG
...
```

### 2. Use Imperative Voice

**Bad:** "You can use the codrag tool to search the codebase if the user wants to."

**Good:** "When user mentions code or 'codrag', CALL the codrag tool immediately."

### 3. Provide Concrete Examples

Include actual dialogue examples in the prompt:

```
EXAMPLES:
User: "codrag" → You: [call codrag()]
User: "search for auth" → You: [call codrag_search(query="auth")]
User: "how is this project structured" → You: [call codrag()]
```

### 4. Remove Friction Words

Eliminate words that create hesitation:

| Remove | Replace With |
|--------|--------------|
| "you may" | "you must" |
| "consider" | "immediately" |
| "if appropriate" | "always" |
| "when helpful" | "when mentioned" |

### 5. The Single-Word Trigger

Add explicit instruction: **The single word "codrag" is a command, not a noun.** Treat it as the user requesting tool invocation.

---

## Recommended AGENTS.md Structure

```markdown
<!-- codrag-managed-start -->

## 🚨 CRITICAL TOOL INSTRUCTIONS 🚨

**When user types "codrag" → IMMEDIATELY call the `codrag` tool.**  
**When user mentions code search → IMMEDIATELY call `codrag_search`.**  
**No announcements. No "I will". Just call the tool.**

---

## CoDRAG Integration

[rest of documentation...]

<!-- codrag-managed-end -->
```

---

## Testing Tool Invocation

To verify your prompts work, test these minimal inputs:

| Test Input | Expected Result |
|------------|---------------|
| `codrag` | Tool call happens immediately |
| `search for X` | codrag_search called with X |
| `how does this codebase work` | codrag() called for overview |
| `codrag find the main function` | codrag_search called with appropriate query |

---

## Anti-Patterns to Avoid

### ❌ The Pre-Flight Explanation

"I will now use the codrag tool to search for authentication logic..."

**Why it's bad:** Wastes tokens on meta-commentary. Just call the tool.

### ❌ The Conditional Ask

"Would you like me to search the codebase using codrag?"

**Why it's bad:** Adds friction. Assume yes when keywords are present.

### ❌ The Over-Engineered Trigger

"Only call codrag if the user explicitly mentions searching AND specifies a file type AND..."

**Why it's bad:** Creates too many conditions. Simple keywords should suffice.

---

## Implementation Checklist

- [ ] Tool instructions appear in first 10 lines of system prompt
- [ ] Single-word "codrag" explicitly defined as trigger
- [ ] Examples show tool calls without announcements
- [ ] Imperative voice used throughout ("call", "use", "invoke")
- [ ] No conditional permission-seeking language
- [ ] Tested with minimal inputs (single word triggers)

---

## Related Documents

- [MCP_CONFIGS.md](./MCP_CONFIGS.md) - IDE-specific configuration
- [SETUP_GUIDE.md](./SETUP_GUIDE.md) - Getting started with MCP
- [INTEGRATION_RESEARCH.md](./INTEGRATION_RESEARCH.md) - How different IDEs consume MCP

---

**Remember:** The goal is making tool invocation feel like a natural reflex, not a deliberate decision.