# SourcePrep Rename Instructions

**TARGET AUDIENCE: AI Coding Agent**

We are officially rebranding the product to **SourcePrep** (formerly CoDRAG / RunPrep). 
This document contains strict instructions on how to execute the rename across the codebase. You must follow these boundaries to ensure the AI Developer Experience (MCP tools) remains intact.

## 🏛️ The Naming Architecture
This is the final, approved naming hierarchy:
- **Brand / App / Project Name**: SourcePrep
- **Website / Domains**: `sourceprep.io`
- **Configuration / Dot-Folders**: `.sourceprep/` (replaces `.codrag/` or `.runprep/`)
- **CLI Command**: `prep` (e.g., `prep init`, `prep build`)
- **MCP Server & Tools**: `prep` (e.g., `prep()`, `prep_search()`, `prep_impact()`)

---

## 🟢 WHAT YOU MUST UPDATE (Search and Replace)

1. **Brand References**:
   - Replace "CoDRAG" and "RunPrep" with "SourcePrep" in all marketing copy, READMEs, UI text, and documentation.
   - Replace "RunPrep with "SourcePrep" in React component text, dashboard headers, and settings pages.
   (most "CoDRAG" has already been replaced)

2. **File Paths & Data Directories**:
   - Change `.runprep/` to `.sourceprep/` (for local workspace config folders).
   - Change `~/.runprep/` to `~/.sourceprep/` (for global OS-level data/cache directories).
   - Update any `.gitignore` entries referencing these folders.

3. **URLs & Domains**:
   - Change `codrag.io` (or `runprep.io`) to `sourceprep.io`.
   - Update API, Docs, Support, and Marketing links (e.g., `docs.sourceprep.io`).

4. **Environment Variables & Config Keys**:
   - Change `CODRAG_` prefixes to `SOURCEPREP_` (e.g., `SOURCEPREP_LICENSE_KEY`, `SOURCEPREP_PROJECT`).
   - Change `codrag_` prefixes in `localStorage` keys or config files to `sourceprep_`.

5. **Recent Documentation / Code Changes**:
   - Any recent edits that changed "Prep" to "RunPrep" (e.g., in `researchSources.ts` or markdown files) should be updated to "SourcePrep" where it refers to the product/brand.

---

## 🛑 WHAT YOU MUST NEVER UPDATE (Do Not Touch)

To preserve the AI tool-calling UX and avoid breaking the integration layer, **DO NOT rename the following**:

1. **MCP Tool Names**:
   - Leave ALL MCP tools exactly as they are. 
   - `prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`, `prep_concepts`.
   - DO NOT change these to `sourceprep_search` or anything else. The semantic shortness of `prep` is intentional.

2. **AI Prompts & `AGENTS.md`**:
   - Do not change instructions that tell the AI to "call the `prep` tool".
   - The phrase "call prep" or "use prep_search" must remain exactly as is.

3. **The CLI Executable**:
   - The binary / CLI command remains `prep`. 
   - E.g., inside `package.json`, `"bin": { "prep": "..." }` should remain `prep`. Do not change the executable to `sourceprep`.

4. **Internal Python/TypeScript MCP Routing**:
   - Any backend routing, function names, or internal tool registries (e.g., `tool_prep_search`, `def prep_search`) that power the MCP server should remain `prep`.

## Execution Summary
When applying this rename, you are updating the **Human-facing Brand** (SourcePrep, `.sourceprep/`, `sourceprep.io`) while completely preserving the **AI-facing API** (`prep`, `prep_search`).


additionally new git repos exiist and we must retain git history for the main repo.
https://github.com/MagneticAnomaly/SourcePrep
https://github.com/MagneticAnomaly/SourcePrep-MCP
https://github.com/MagneticAnomaly/SourcePrep-MCP-DEV
https://github.com/MagneticAnomaly/SourcePrep-deploy