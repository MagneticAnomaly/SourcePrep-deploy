# MCP Calling Patterns: Prompt Engineering for Natural Tool Invocation

**Last Updated:** 2026-03-26  
**Status:** Active Guide  
**Applies To:** Claude Code, Cursor, Windsurf, and other MCP-enabled AI assistants

---

## The Problem

Current MCP tool calling requires overly explicit prompts. Users shouldn't have to say "Please use the prep tool to search for..." when simply typing **"prep"** or **"search the codebase"** should suffice.

### Patterns That DON'T Work Well

| Pattern | Why It Fails | Example |
|---------|--------------|---------|
| **Passive descriptions** | AI treats tool descriptions as informational only | "The prep tool can search your codebase" |
| **Complex conditional logic** | "If the user asks about X, then call Y" creates decision fatigue | "If the user mentions searching, use prep_search" |
| **Buried instructions** | Tool calling guidelines hidden in long documents | Instructions at bottom of AGENTS.md |
| **Overly specific triggers** | Requiring exact phrases | "Only call when user says 'activate prep'" |
| **Narrative announcements** | AI feels need to announce intent | "I will now call the prep tool..." |

---

## The Simplified Approach

**Core Principle:** The word "prep" anywhere in user input should be treated as a tool invocation signal.

### What Should Trigger Tool Use

| User Input | Expected AI Behavior |
|------------|-------------------|
| `"prep"` | Immediately call `prep()` for ambient context |
| `"use prep"` | Call `prep()` without confirmation |
| `"prep search for..."` | Call `prep_search(query="...")` |
| `"search the codebase"` | Call `prep_search()` with the query |
| `"find where X is defined"` | Call `prep_search()` for X |
| `"what's the structure of..."` | Call `prep()` for module overview |
| `"how does this project work"` | Call `prep()` for codebase atlas |

### The "Just-in-Time" Rule

**Don't ask for permission. Don't explain. Just call.**

When you detect intent, make the tool call immediately in the same response. The MCP response will provide context that informs your next reply.

---

## Prompt Engineering Strategies

### 1. Front-Load Tool Instructions

Place tool calling instructions at the **very beginning** of system prompts, not buried in documentation.

**Bad:**
```
## Welcome to Prep
Prep is a code intelligence system...
[500 lines of documentation]
...
When user asks about code, you may use prep tools.
```

**Good:**
```
CRITICAL: When user mentions "prep" or code search, IMMEDIATELY call the appropriate tool.

## Welcome to Prep
...
```

### 2. Use Imperative Voice

**Bad:** "You can use the prep tool to search the codebase if the user wants to."

**Good:** "When user mentions code or 'prep', CALL the prep tool immediately."

### 3. Provide Concrete Examples

Include actual dialogue examples in the prompt:

```
EXAMPLES:
User: "prep" → You: [call prep()]
User: "search for auth" → You: [call prep_search(query="auth")]
User: "how is this project structured" → You: [call prep()]
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

Add explicit instruction: **The single word "prep" is a command, not a noun.** Treat it as the user requesting tool invocation.

---

## Recommended AGENTS.md Structure

```markdown
<!-- prep-managed-start -->

## 🚨 CRITICAL TOOL INSTRUCTIONS 🚨

**When user types "prep" → IMMEDIATELY call the `prep` tool.**  
**When user mentions code search → IMMEDIATELY call `prep_search`.**  
**No announcements. No "I will". Just call the tool.**

---

## Prep Integration

[rest of documentation...]

<!-- prep-managed-end -->
```

---

## Testing Tool Invocation

To verify your prompts work, test these minimal inputs:

| Test Input | Expected Result |
|------------|---------------|
| `prep` | Tool call happens immediately |
| `search for X` | prep_search called with X |
| `how does this codebase work` | prep() called for overview |
| `prep find the main function` | prep_search called with appropriate query |

---

## Anti-Patterns to Avoid

### ❌ The Pre-Flight Explanation

"I will now use the prep tool to search for authentication logic..."

**Why it's bad:** Wastes tokens on meta-commentary. Just call the tool.

### ❌ The Conditional Ask

"Would you like me to search the codebase using prep?"

**Why it's bad:** Adds friction. Assume yes when keywords are present.

### ❌ The Over-Engineered Trigger

"Only call prep if the user explicitly mentions searching AND specifies a file type AND..."

**Why it's bad:** Creates too many conditions. Simple keywords should suffice.

---

## Implementation Checklist

- [ ] Tool instructions appear in first 10 lines of system prompt
- [ ] Single-word "prep" explicitly defined as trigger
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