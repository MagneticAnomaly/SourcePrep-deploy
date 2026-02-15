# Organic/Personal Post Draft for r/OpenAI

## Title Options
1. **Stop guessing imports: A local tool to feed o1/4o structural context**
2. **I built a "Context Pruner" for ChatGPT coding sessions**

## Body Structure

### The Workflow
Me: *Pastes file*
ChatGPT: "I don't see the definition for `User`."
Me: *Pastes `models.py`*
ChatGPT: "I don't see the definition for `BaseModel`."
Me: *Sighs.*

### The Solution
**CoDRAG** automates this. It builds a graph locally. You ask a question, it finds the chain of dependencies, and gives you a concise prompt to paste (or feeds it via MCP if you use a client).

It saves me so much copy-pasting time.

**Link:** [Link]

## Tone
Relatable frustration.
