# Prep UI Component Architecture

This document describes the foundational component architecture for the Prep dashboard, derived from Phase 01 (Foundation) and Phase 02 (Dashboard) specifications.

## Overview

The component library is organized into five categories:

```
src/components/
├── status/        # Index/build status indicators
├── navigation/    # App shell, sidebar, tabs
├── search/        # Search input, results, chunk viewer
├── context/       # Context assembly output
└── patterns/      # Shared state patterns (empty, loading, error)
```

## Component Inventory

### Status Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `StatusBadge` | Visual status indicator (Fresh/Stale/Building/Error) | `status`, `showLabel` |
| `StatusCard` | Project status overview card | `projectName`, `status`, `lastBuildAt`, `chunkCount`, `error` |
| `BuildProgress` | Build progress with phases and counters | `phase`, `percent`, `counts` |

### Navigation Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `AppShell` | Main layout container (sidebar + tabs + content) | `sidebar`, `tabs`, `children` |
| `Sidebar` | Collapsible sidebar container | `collapsed`, `onCollapseToggle`, `children` |
| `ProjectList` | Project list with add action | `projects`, `selectedProjectId`, `onProjectSelect`, `onAddProject` |
| `ProjectTabs` | Open project tabs with close | `tabs`, `activeTabId`, `onTabSelect`, `onTabClose` |

### Search Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `SearchInput` | Query input with submit | `value`, `onChange`, `onSubmit`, `loading` |
| `SearchResultRow` | Single search result row | `result`, `showScore`, `onClick`, `selected` |
| `ChunkViewer` | Full chunk detail panel | `chunk`, `onClose` |

### Context Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `ContextViewer` | Assembled context output | `context`, `chunks`, `totalChars`, `estimatedTokens`, `showSources`, `showScores` |
| `CitationBlock` | Source attribution | `sourcePath`, `span`, `score`, `showScore` |
| `CopyButton` | Copy-to-clipboard action | `text`, `label` |

### Pattern Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `EmptyState` | No data placeholder | `title`, `description`, `action`, `icon` |
| `LoadingState` | Loading indicator | `message`, `variant` (card/inline/fullscreen) |
| `ErrorState` | Actionable error display | `title`, `error`, `onRetry`, `onDismiss` |

## Type Definitions

Core types are defined in `src/types.ts`:

- `StatusState`: `'fresh' | 'stale' | 'building' | 'pending' | 'error' | 'disabled'`
- `SearchResult`: Search result with chunk_id, source_path, span, preview, score
- `CodeChunk`: Code chunk for display with content and language
- `ProjectSummary`: Project metadata for list display

## Design Principles

### 1. Tremor-First
Components use Tremor primitives (Card, Badge, Table, Button, etc.) as the base. Custom components are only created when:
- The pattern is not available in Tremor
- It is core to Prep (e.g., ChunkViewer, CitationBlock)

### 2. Wireframe-Ready
Components are structural and functional. Final styling will be applied after visual direction is chosen (Phase 13). All components use:
- CSS class hooks (`prep-*` prefixes) for later styling
- Design token CSS variables from `tokens/index.css`

### 3. State-Driven
Every component supports the four UX states from Phase 02:
- **Loading**: Show skeleton or spinner
- **Empty**: Show actionable empty state
- **Ready**: Show data
- **Error**: Show actionable error with code + message + hint

### 4. Trust-First UX
Components prioritize:
- Clear status/freshness indicators
- Inspectability (source paths, spans, scores)
- Actionable errors with hints

## Storybook Organization

Stories are organized to match the component structure:

```
stories/
├── Introduction.mdx
├── status/
│   ├── StatusBadge.stories.tsx
│   ├── StatusCard.stories.tsx
│   └── BuildProgress.stories.tsx
├── navigation/
│   └── AppShell.stories.tsx
├── search/
│   └── SearchComponents.stories.tsx
├── context/
│   └── ContextComponents.stories.tsx
└── patterns/
    └── StatePatterns.stories.tsx
```

## API Alignment

Components are designed to consume the Prep API response shapes defined in Phase 02:

```typescript
// API response envelope
{ success: true, data: {...}, error: null }
{ success: false, data: null, error: { code, message, hint } }

// Status response
{ building, index: { exists, total_chunks, ... }, trace: {...} }

// Search response
{ results: [{ chunk_id, source_path, span, preview, score }] }

// Context response
{ context: "...", chunks: [...], total_chars, estimated_tokens }
```

## Next Steps

1. **Styling Phase**: After visual direction is selected, apply design tokens
2. **API Integration**: Connect components to actual Prep daemon
3. **Page Composition**: Build page-level components (StatusPage, SearchPage, etc.)
4. **Accessibility**: Audit keyboard navigation and ARIA attributes
