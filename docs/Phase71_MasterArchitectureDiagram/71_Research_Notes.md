# Phase 71: Master Architecture Diagram — Research Notes

## Research Date: 2026-04-03

## Technology Landscape

### Interactive Graph Libraries for React

| Library | Best For | Rendering | DnD Support | Custom Nodes | Performance |
|:---|:---|:---|:---|:---|:---|
| **React Flow (`@xyflow/react` v12)** | Node editors, architecture diagrams | SVG/HTML | ✅ Native | ✅ Full React components | Good (viewport virtualization) |
| `react-force-graph` | Data viz, large networks | Canvas/WebGL | ❌ Limited | ❌ | Excellent |
| Custom D3 | Fully custom layouts | SVG/Canvas | Manual | Manual | Variable |
| Mermaid.js | Static diagram-as-code | SVG | ❌ | ❌ | N/A |
| D2 | Architecture documentation | SVG | ❌ | ❌ | N/A |

**Decision: React Flow** — because we need an interactive *editor*, not just a visualization. Users need to drag nodes, add sticky notes to archicture nodes, collapse/expand modules, and click to inspect.

### React Flow v12 Key Features
- Package rename: `reactflow` → `@xyflow/react`
- Built-in dark mode via `colorMode` prop + CSS variables
- New hooks: `useHandleConnections`, `useNodesData`, `updateNode`, `updateNodeData`
- SSR/SSG support
- Improved TypeScript support with TSDoc
- Subflows via `parentId` + `extent: 'parent'`
- Annotations via custom nodes (no dedicated annotation component)

### Best Practices (2025/2026)
1. **State**: Use Zustand for complex apps (React Flow uses it internally)
2. **Re-renders**: Wrap all custom nodes/edges in `React.memo`
3. **Interactivity**: Add `nodrag` class to inner form/interactive elements
4. **Connections**: Use unique `id`s for handles
5. **DND**: Use `screenToFlowPosition` to map coordinates
6. **Scaling**: Use viewport-based virtual rendering for large graphs
7. **Layout**: Use ELK.js for hierarchical auto-layout

### Auto-Layout Options
- **ELK.js** (Eclipse Layout Kernel) — hierarchical/layered layout, excellent for module dependency graphs
- **Dagre** — simpler directed graph layout, less flexible
- **d3-force** — physics-based, good for organic exploration but less structured

**Decision: ELK.js** for the primary "organize" button (produces clean hierarchical layouts), with possible d3-force toggle for exploration mode in V2.

## Academic/Industry References

### Architecture Visualization Tools
- **Sourcetrail** — archived but pioneering interactive code exploration with graph-based UI
- **CodeScene** — behavioral code analysis with architectural visualization
- **Structure101** — structure visualization with dependency analysis
- **CodeMap** — VS Code extension for code structure visualization

### Key Insights
1. Architecture diagrams should be **composable** — users should be able to zoom from high-level modules down to individual files
2. **Edge aggregation** is critical — showing every individual import between two modules creates visual noise
3. **Persistence** matters — the diagram becomes useless if positions reset every reload
4. **Annotations as first-class citizens** — the diagram is a communication tool, not just a visualization

## Prep Data Available

### Existing Backend Data (no new analysis needed)

1. **Module Synthesis** (`/projects/{id}/modules/status`)
   - Clustered modules with file assignments
   - Module names and descriptions

2. **Trace Graph** (`/projects/{id}/trace/*`)
   - All nodes (files, symbols, external modules)
   - All edges (imports, calls, implements, documented_by)
   - Hub files (highest in-degree)
   - Impact graph (reverse-dependency BFS)
   - File-to-file edge queries

3. **Atlas** (`/projects/{id}/atlas`)
   - LLM-generated architectural overview
   - Segment-level descriptions for workspace areas
   - Role-based atlas projections

4. **Augmentation/Epistemic**
   - Per-file summaries and confidence scores
   - Epistemic enrichment metadata

5. **Audit Findings**
   - Architecture issues linked to specific files
   - Tech debt hotspots

### New Composite Endpoint Design

```python
# GET /projects/{id}/architecture/graph
{
  "modules": [
    {
      "id": "mod_1",
      "name": "Authentication",
      "description": "User auth, session management, JWT tokens",
      "files": ["src/auth/login.py", "src/auth/session.py", ...],
      "file_count": 12,
      "hub_files": ["src/auth/login.py"],
      "atlas_section": "...",
    }
  ],
  "files": [
    {
      "id": "file:src/auth/login.py",
      "path": "src/auth/login.py",
      "module_id": "mod_1",
      "language": "python",
      "hub_score": 15,
      "confidence": 0.87,
      "summary": "Handles user login flows...",
      "line_count": 340,
    }
  ],
  "edges": [
    {
      "source_module": "mod_1",
      "target_module": "mod_2", 
      "count": 5,
      "kinds": ["imports", "calls"],
      "file_edges": [
        {"source": "src/auth/login.py", "target": "src/db/users.py", "kind": "imports"}
      ]
    }
  ],
  "stats": {
    "total_modules": 8,
    "total_files": 245,
    "total_edges": 1200,
    "generated_at": "2026-04-03T20:30:00Z"
  }
}
```

## UI Inspiration

### Node Card Design
- Rounded corners, subtle shadow
- Left accent color by language/category
- Hover: glow effect, show connection count badges
- Selected: highlighted border, sidebar opens
- Hub files: animated subtle pulse/gradient ring

### Module Group Design
- Dashed border container
- Collapsible: shows file count badge when collapsed
- Header bar with module name + expand/collapse toggle
- Light background tint matching module color

### Annotation Design
- Yellow/pastel sticky-note appearance
- Editable on double-click
- Auto-resize to content
- Optional connection line to a specific node

### Edge Design
- Straight/bezier based on distance
- Color-coded: blue (imports), green (calls), orange (inferred), gray (implements)
- Aggregated module edges: thicker stroke + count label
- Hover: highlight full path, show edge metadata
