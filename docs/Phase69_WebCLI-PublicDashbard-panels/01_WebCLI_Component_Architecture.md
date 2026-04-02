# Phase 69: WebCLI & Public Dashboard Panels

## Objective
Develop a robust, reusable set of React components for the marketing and documentation sites (`websites/apps/marketing`, `websites/apps/docs`) that realistically simulate and animate agentic terminal interactions. 

The immediate goal is to build an `AnimatedCLI` component that mimics the aesthetic of Claude Code—an active, dynamic terminal showing the agent interacting with the CoDRAG MCP server in real-time. Over time, this component system will expand to include IDE wrappers (e.g., Cursor) and isolated interactive panels from the actual application dashboard.

## Phase 1: The Animated CLI Component

### Concept
Rather than static images or pre-rendered generic videos, we will build a data-driven React component. It accepts an array of "Terminal Events" and plays them back with realistic timing, typing delays, and status indicators.

### Key Visual Language (Claude Code Style)
*   **Typography:** Strict monospace for the inner frame (`Fira Code`, `JetBrains Mono`, or system monospace).
*   **Prompts:** `> ` with user text, often styled distinctly.
*   **Tool Execution:** Clear visual separation when the agent reaches out to CoDRAG. E.g., a muted or distinct color block:
    *   *Executing `codrag_search`...*  
    *   *Received 5 context chunks (1842 tokens)*
*   **LLM Output:** Typewriter effect for prose, syntax highlighting for code blocks dropped into the terminal.

### Architecture Proposal: `packages/ui`
We will build this in `packages/ui/src/components/marketing` (or `console`) so it can be shared across the entire workspace.

1.  **`packages/ui/src/components/console/AnimatedCLI.tsx`**
    *   The core playback engine. Manages state (current step, visible text).
    *   Uses a simple state machine and hooks (`useInterval`, `setTimeout`) to advance the script.
2.  **`packages/ui/src/components/console/AgentScript.ts`**
    *   Type definitions for the script events.
    *   ```typescript
        export type ScriptEvent = 
          | { type: 'input'; text: string; typingSpeedMs?: number }
          | { type: 'tool_start'; toolName: string; args: string }
          | { type: 'tool_complete'; resultSummary: string; responseTimeMs: number }
          | { type: 'output'; text: string; delayMs?: number };
        ```
3.  **`packages/ui/src/components/console/WindowFrame.tsx`**
    *   A generic macOS-style terminal window wrapper (traffic light dots, subtle border, blur backdrop). 
    *   Later, we will add an `IDEFrame` wrapper for the Cursor aesthetic.

## Phase 2: Implementation & Showcase

We will build the `AnimatedCLI` and deploy a test showcase on the Marketing site (`/compare/codrag-vs-greptile` or the homepage) to demonstrate CoDRAG acting as the context engine behind a terminal agent.

## Future: Phase 3 (Public Dashboard Panels)
As part of the larger WebCLI initiative described, we will eventually extract the actual React dashboard panels (e.g., the Trace Graph viewer or Agent Role selector) to run in "Showcase Mode" on the public sites, driven by mocked live state instead of real backend processes.
