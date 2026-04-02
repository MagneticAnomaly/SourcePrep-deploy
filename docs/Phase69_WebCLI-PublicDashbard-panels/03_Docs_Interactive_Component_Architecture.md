# Documentation Site: Interactive Component Integration Plan

The marketing variants were focused on flash and persuasive scenarios. For the **Documentation** pages, our goal shifts entirely to descriptive action: "Show me exactly how this tool responds so I know what to expect."

Because we want these interactive components embedded widely (almost one per page), we must solve the architectural pattern of how to author them comfortably.

## 1. The Architectural Solution: MDX Shortcodes

To scale the documentation safely, we will use **MDX Shortcodes**. This prevents authors from having to write raw React components inside Markdown.

1. **Global Provider**: Update the `websites/apps/docs` MDX provider to globally register three interactive components: `<AnimatedCLI />`, `<AnimatedIDE />`, and `<StorybookEmbed />`.
2. **Decoupled Payloads**: Move the data payloads (`CliScript` objects) into co-located JSON/TS files (`src/demo-data.ts`) specific to the documentation pages so they don't pollute the generic UI library.
3. **Clean Authoring**: Writers use clean, short tags inside `.mdx` files:
   ```mdx
   ### Structural Search

   Use the `codrag_search` tool to find exact AST context.
   
   <AnimatedCLI script={docsSearchDemo} theme="dark" />
   ```

**The `<StorybookEmbed />` Strategy:**
For dashboard/UI component documentation, we want interactive React components via Storybook. 
We will build a `<StorybookEmbed componentId="pipeline-status" />` wrapper component for the docs site that points to our hosted Storybook instance via an `iframe`. This ensures the docs always show the *living* UI component, not stale screenshots.

---

## 2. Comprehensive Content Mapping

Below is the proposed mapping of which interactive elements belong on which core documentation pages.

### Getting Started & Concepts
| Route | Component Needed | Description |
|-------|-----------------|-------------|
| `/getting-started` | `AnimatedCLI` | Shows the quick extraction sequence: `npx @codrag/cli init`, showing the progress bar and exact output when the daemon starts indexing. |
| `/concepts/trace-graph` | `StorybookEmbed` | Embeds the actual Code Graph Visualization component from the UI library, allowing the user to click nodes and see relationships. |
| `/concepts/role-aware` | `AnimatedIDE` | Split pane. Left side: Agent asks for roles. Right side shows the context shrinking heavily when the "Security Agent" scope is actively applied. |

### CLI & Tools Documentation
| Route | Component Needed | Description |
|-------|-----------------|-------------|
| `/cli/codrag` | `AnimatedCLI` | Shows the ambient context payload exactly as it appears: listing hub files, dependency graph metrics, and focus areas. |
| `/cli/codrag_search` | `AnimatedCLI` | Shows a natural language query retrieving an exact interface definition (AST) vs a regex failure. |
| `/cli/codrag_impact` | `AnimatedCLI` | Shows the 3-hop traversal output of `codrag_impact` on a core file, highlighting direct and transitive dependents. |
| `/cli/codrag_audit` | `AnimatedIDE` | Shows the agent triggering `codrag_audit`, and the sidebar highlighting tech debt findings while the core editor opens the offending file. |
| `/cli/codrag_observe` | `AnimatedCLI` | Shows a developer recording a decision (`saving [STALE] flag memory`), fast-forwarding, and retrieving it. |

### MCP Integrations
| Route | Component Needed | Description |
|-------|-----------------|-------------|
| `/mcp/windsurf` | `AnimatedIDE` | A Windsurf-themed `<AnimatedIDE>` layout showing the Cascade agent seamlessly picking up the MCP tools. |
| `/mcp/cursor` | `AnimatedIDE` | A Cursor-themed `<AnimatedIDE>` layout showing Cursor Composer reading a multi-file dependency graph via CoDRAG. |
| `/mcp/claude-desktop` | `AnimatedCLI` | Shows the standard Claude Desktop chat UI reading local desktop files via CoDRAG. |

### Dashboard & UI Documentation
*(Heavily reliant on the `<StorybookEmbed />` system)*

| Route | Component Needed | Description |
|-------|-----------------|-------------|
| `/dashboard/pipeline` | `StorybookEmbed` | Embeds the `<PipelineDashboard />` component with active, mock Redis data. |
| `/dashboard/server-status` | `StorybookEmbed` | Embeds the `<ServerStatusCard />` showing memory footprint and latency gauges. |
| `/dashboard/knowledge-trees` | `StorybookEmbed` | Embeds the Agent Knowledge Scope UI so users can interact with the folder inclusion/exclusion toggles. |
