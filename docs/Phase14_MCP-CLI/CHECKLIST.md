# Checklist: Phase 14 (MCP-CLI)

## 1. Core Refactoring
- [x] **Verify Core Independence**: Ensure `CodeIndex` and `TraceIndex` can be instantiated easily without the full Server `_config` global dependency.
    - *Note*: `server.py` relies on a global `_config`. `CodeIndex` takes params in `__init__`. We need to ensure `CodeIndex` doesn't secretly rely on global state.
- [x] **Async Wrappers**: `DirectMCPServer` wraps blocking calls in `asyncio.to_thread`.

## 2. Direct MCP Implementation
- [x] **Create `src/prep/mcp_direct.py`**:
    - [x] Implement `DirectMCPServer` class.
    - [x] Implement `tool_status`, `tool_build`, `tool_search`, `tool_context`.
    - [x] Add "Auto-detect root" logic (CWD).
- [x] **Unified Tool Definitions**: Extract `TOOLS` list to a shared file (`src/prep/mcp_tools.py`) to avoid duplication between `mcp_server.py` and `mcp_direct.py`.

## 3. CLI Updates
- [x] **Update `cli.py`**:
    - [x] Add `--mode direct` to `mcp` command.
    - [x] Make `--daemon` optional.
    - [x] If direct mode, instantiate `DirectMCPServer` instead of `MCPServer`.
- [x] **Config Generator**:
    - [x] Update `mcp-config` to generate configs that use direct mode (no `--daemon` arg, just `prep mcp`).

## 4. "Zero Config" Experience
- [x] **Default Settings**: Defaults are generated via `repo_policy.json` (repo profiling) and now exclude `.runprep/` by default.
- [x] **Auto-Discovery**: Direct mode uses CWD as `repo_root` and defaults index storage to `<repo_root>/.runprep/index`.

## 5. Testing
- [x] **Integration Test**: Created `tests/test_mcp_direct_e2e.py` to verify full flow.
- [x] **Manual Test**: Created `tests/test_mcp_direct_manual.py` for quick verification.

## 6. Distribution
- [ ] **Pip Package**: Ensure `pip install prep` installs all dependencies needed for Direct Mode (numpy, etc.).
- [ ] **NPM Wrapper (Optional)**: Consider `npx prep` wrapper if targeting JS devs.

## 7. Documentation
- [x] **Update README**: "How to use with Cursor/Windsurf (No Server Required)".
- [x] **Dashboard Notes**: Added `FRONTEND_INTEGRATION.md`.
