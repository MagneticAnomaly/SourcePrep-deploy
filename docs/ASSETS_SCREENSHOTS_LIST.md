# Prep Screenshot & Image Assets Checklist

This document consolidates all the required screenshots and image assets needed across the marketing site and documentation. Since we want to upload images once and use them in multiple places, this serves as the master list.

All images should be saved to `websites/apps/docs/public/images/` and `websites/apps/marketing/public/images/` (or a shared CDN/asset directory in the future) using the exact filenames listed below.

## 1. Marketing Site (Landing Page & Feature Blocks)

| Filename | Description / Content | Used In |
|---|---|---|
| `hero-dashboard-preview.png` | A hero-quality, stylized screenshot of the Prep dashboard. Should show the two-pane layout with the Knowledge Pipeline active and a search result visible. | `MarketingHero.tsx` |
| `feature-graph-trace.png` | A visual representation or clean screenshot of the structural code graph (nodes/edges or the trace expansion panel). | `FeatureBlocks.tsx` (Graph Enrichment / Structural Graph) |
| `feature-path-weights.png` | A focused screenshot of the Path Weights configuration panel showing sliders/badges for different directories. | `FeatureBlocks.tsx` (Path Weights) |
| `feature-clara-compression.png` | A focused screenshot or graphic showing the CLaRa compression ratio (e.g., "16,000 tokens → 1,200 tokens"). | `FeatureBlocks.tsx` (10-16x Compression) |
| `integration-cursor-windsurf.png` | A split screenshot showing the MCP config in Windsurf and the server status in Cursor. | `page.tsx` (Works where you work section) |

## 2. Documentation Site

| Filename | Description / Content | Used In |
|---|---|---|
| `docs-cursor-settings.png` | Cursor Settings > Features > MCP Servers screen. | `mcp/cursor/page.tsx` |
| `docs-cursor-add-modal.png` | The "Add MCP Server" modal in Cursor filled out with Prep details. | `mcp/cursor/page.tsx` |
| `docs-cursor-connected.png` | The green dot / "Connected" status indicator in Cursor. | `mcp/cursor/page.tsx` |
| `docs-windsurf-config.png` | Code snippet/screenshot of the `.codeium/windsurf/mcp_config.json` file. | `mcp/windsurf/page.tsx` |
| `docs-dashboard-main.png` | The main two-pane dashboard view (Overview). | `dashboard/page.tsx`, `getting-started/page.tsx` |
| `docs-dashboard-add-project.png` | The "Add Project" modal/dialog. | `dashboard/projects/page.tsx` |
| `docs-dashboard-pipeline.png` | The Knowledge Pipeline view showing indexing status and passes. | `dashboard/projects/page.tsx`, `dashboard/page.tsx` |
| `docs-dashboard-graph-scope.png` | The Graph Scope / Directory tree view in the dashboard. | `dashboard/projects/page.tsx`, `dashboard/page.tsx` |
| `docs-dashboard-settings.png` | The Project Settings panel. | `dashboard/projects/page.tsx` |
| `docs-dashboard-search.png` | The semantic search testing panel with a query and results. | `dashboard/page.tsx` |
| `docs-getting-started-editor.png` | AI assistant chat panel (Cursor/Windsurf) showing Prep tool being used. | `getting-started/page.tsx` |
| `docs-clara-terminal.png` | Terminal screenshot showing the CLaRa docker container running/starting. | `guides/clara/page.tsx` |
| `docs-clara-settings.png` | Prep settings panel showing CLaRa enabled. | `guides/clara/page.tsx` |
| `docs-path-weights-badges.png` | Close-up of the directory tree showing multiplier badges (e.g., 1.5x, 0.5x). | `guides/path-weights/page.tsx` |
| `docs-models-settings.png` | Settings > AI Models panel showing local/cloud provider configuration. | `guides/models/page.tsx` |

## Image Capture Guidelines
- **Resolution**: Capture at 2x (Retina) resolution for crisp rendering on high-DPI displays.
- **Theme**: Use the dark theme for all editor and dashboard screenshots to maintain consistency with the Prep brand.
- **Aspect Ratio**: Keep hero/feature images relatively wide (16:9 or 21:9) where possible, and UI detail shots cropped tightly to the relevant feature.
- **Anonymization**: Ensure no sensitive personal code or tokens are visible in the screenshots. Use the Prep repo itself as the subject matter for the screenshots.
