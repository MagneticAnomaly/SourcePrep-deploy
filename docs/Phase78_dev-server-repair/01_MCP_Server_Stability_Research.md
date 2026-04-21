# Phase 78 — MCP Server Stability Research & Dev Workflow Optimization

**Research Document 1 of X** | Phase 78: Development Environment Stability & Hot-Reload Strategy  
**Date:** 2025-01-09  
**Status:** Active Investigation  
**Observer:** Claude (AI Assistant) via Claude Code CLI  

---

## Executive Summary

During routine CoDRAG MCP tool usage, a critical stability pattern emerged: the MCP server successfully processes an initial request, then enters a degraded state where subsequent requests fail with cascading errors. This document captures observed behaviors, hypothesizes root causes, and outlines research directions for improving development workflow stability.

**Key Finding:** The MCP server exhibits a "one-and-done" failure pattern—functional on first request, then progressively failing until complete disconnection.

---

## Observed Error Sequence

### Session Timeline (Terminal Session, ~3:00-3:30 PM)

| Timestamp | Action | Result | Notes |
|-----------|--------|--------|-------|
| T+0 | Start `dev.sh` in separate terminal | ✅ Daemon starts on :8400 | HTTP health checks pass |
| T+1 | New Claude Code session | ✅ MCP server spawns | Process PID 7784 observed |
| T+2 | **First `codrag` call** | ✅ **Full success** | Complete project structure returned (~400 lines) |
| T+3 | **Second `codrag` call** | ❌ **Timeout** | "Context server request timeout" after ~30s |
| T+4 | **Third `codrag` call** | ❌ **Channel error** | "sending into a closed channel" |
| T+5 | **Fourth+ `codrag` calls** | ❌ **Server down** | "server shut down" |

### Error Messages Analysis

1. **"Context server request timeout"**
   - Suggests the request was sent but response never returned
   - Indicates potential deadlock or infinite loop in request handling

2. **"sending into a closed channel"**
   - Internal Go error message (from Claude Code's MCP client)
   - Indicates the communication channel between Claude and MCP server was closed
   - Likely the MCP server process crashed or the stdio pipe broke

3. **"server shut down"**
   - Final state: MCP client recognizes server is no longer responding
   - Connection is permanently lost until new session

---

## Root Cause Hypotheses

### Hypothesis 1: Background Code Modification (Primary Suspect)

**Mechanism:**  
During active development, Python source files in `/src/codrag/` are modified (via IDE autosave, git operations, or explicit edits). Python's import system may cache modules in ways that cause:
- Running code to reference stale bytecode
- Import errors if module structure changes
- Resource leaks when modules are reloaded

**Evidence Supporting:**
- `dev.sh` typically runs with `--reload` flag (hot-reload mode)
- Multiple Claude Code windows accessing same codebase simultaneously
- Pattern matches "works once, then fails" suggesting runtime state corruption

**Evidence Against:**
- No Python `ImportError` or `ModuleNotFoundError` observed
- First request works (suggests imports are valid at startup)

### Hypothesis 2: Async Event Loop Corruption

**Mechanism:**  
The MCP server uses `asyncio` for handling requests. If the event loop enters a bad state:
- Subsequent coroutines may not execute
- Event loop may be closed or blocked
- stdio transport may be exhausted

**Evidence Supporting:**
- Timeout on second request suggests event loop not processing
- "Closed channel" suggests transport layer breakdown
- Pattern is consistent with event loop being blocked or closed

### Hypothesis 3: Resource Exhaustion

**Mechanism:**  
Each request may leak resources (file handles, memory, HTTP connections to daemon) that accumulate until the server can no longer function.

**Evidence Supporting:**
- First request always succeeds (fresh process)
- Progressive degradation (timeout → channel error → shutdown)
- Daemon remains healthy on :8400 (suggests client-side issue)

**Evidence Against:**
- No `EMFILE` (too many open files) errors observed
- Memory usage appeared stable in process list

### Hypothesis 4: Multiple MCP Process Interference

**Observation:** At one point, **three** `codrag mcp` processes were simultaneously running:
```
PID 20648 - codrag mcp
PID 20623 - codrag mcp  
PID 8474  - codrag mcp
```

**Mechanism:**  
Multiple MCP servers competing for resources or conflicting over state files. Could cause race conditions on:
- Log file writes
- Project registry access
- stdio/transport handling

---

## Impact on Development Workflow

### Current Pain Points

1. **IDE Restart Tax**: Every code change requires restarting Claude Code to restore MCP connection
2. **Context Loss**: Restarting clears conversation history and assistant state
3. **Development Velocity**: Context switching between editor and terminal to restart
4. **Uncertainty**: Never clear if a bug is in the code being written or the MCP connection

### Affected Workflows

| Workflow | Impact | Frequency |
|----------|--------|-----------|
| Testing MCP tool changes | High | Every iteration |
| Dogfooding CoDRAG features | High | Continuous |
| Multi-file refactoring | Medium | Per session |
| Documentation writing | Low | Background |

---

## Research Directions

### Direction 1: Reproduction & Isolation

**Goal:** Create minimal reproduction of the failure pattern

**Experiments:**
1. Start MCP server manually in foreground with debug logging
2. Send sequential JSON-RPC requests via netcat/curl
3. Observe if failure occurs without Claude Code in the loop
4. Test with file watcher disabled vs. enabled

**Success Criteria:** Can reproduce failure outside of Claude Code context

### Direction 2: Process Lifecycle Analysis

**Goal:** Understand why multiple MCP processes accumulate

**Experiments:**
1. Monitor process tree during normal usage
2. Check if old processes are orphaned (PPID = 1) or zombies
3. Test if `--mode direct` vs `--mode server` affects stability
4. Profile stdio transport lifecycle

**Success Criteria:** Identify why cleanup is incomplete

### Direction 3: Hot-Reload Strategy Design

**Goal:** Design development workflow that doesn't require IDE restart

**Approaches to Evaluate:**

| Approach | Mechanism | Pros | Cons |
|----------|-----------|------|------|
| **HTTP Transport** | Use `--transport http` instead of stdio | Multiple clients, no IDE restart | Requires port management, CORS |
| **Watchdog Wrapper** | Shell script restarts MCP on crash | Transparent recovery | State loss, startup latency |
| **Dual Mode Dev** | Separate dev/prod MCP configs | Stable prod, flexible dev | Config complexity |
| **In-Process Mode** | Claude Code runs Python directly | No separate process | Security, isolation concerns |

### Direction 4: Graceful Degradation

**Goal:** Make MCP server resilient to failures

**Features to Research:**
- Circuit breaker pattern for daemon connections
- Request timeout handling with cleanup
- Health check endpoint for external monitoring
- Automatic restart signal to parent process

---

## Proposed Dev Workflow Improvements

### Short-term (Immediate)

1. **Add `--log-file` to MCP wrapper**
   ```bash
   # In codrag-mcp-wrapper.sh
   exec "$SCRIPT_DIR/.venv/bin/codrag" mcp --log-file ~/.prep/logs/mcp-$(date +%s).log "$@"
   ```

2. **Document "Known Issue" in AGENTS.md**
   - Warn developers about restart requirement
   - Suggest workarounds (HTTP mode, separate terminal)

3. **Create MCP Health Check Script**
   ```bash
   #!/bin/bash
   # Quick check if MCP is responsive
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | codrag mcp --mode direct
   ```

### Medium-term (Next Sprint)

1. **Implement HTTP Transport as Default for Dev**
   - Change `.claude/mcp.json` to use SSE transport
   - Run MCP server in persistent terminal
   - Update `dev.sh` to launch MCP alongside daemon

2. **Add MCP Process Monitoring to Dashboard**
   - Show active MCP connections
   - Display last request time/health
   - Manual "Restart MCP" button

3. **Hot-Reload Without Restart**
   - Research if MCP server can reload modules safely
   - Implement file watcher with graceful restart

### Long-term (Architecture)

1. **Persistent MCP Server Mode**
   - Single MCP server process handles multiple projects
   - Survives individual client disconnections
   - State maintained across IDE restarts

2. **Development Mode Protocol**
   - Special protocol messages for "reload module X"
   - Isolated sandbox for testing new tool implementations
   - Integration with test framework

---

## Open Questions

1. **Does the failure occur with `--mode direct`?**  
   Direct mode doesn't require daemon—would isolate whether issue is in MCP layer or daemon communication layer.

2. **What does `codrag mcp --debug` reveal?**  
   Debug logging may show exception traceback that's currently swallowed.

3. **Is the issue specific to `codrag` tool or all tools?**  
   Does `codrag_search`, `codrag_impact`, etc. exhibit same pattern?

4. **Does daemon restart correlate with MCP failures?**  
   Check if `dev.sh` reloads are triggering the failures.

5. **What is the stdio buffer state at failure?**  
   Are we hitting OS pipe buffer limits?

---

## Appendix: Technical Details

### Environment
- **OS:** macOS
- **Python:** 3.11
- **CoDRAG Version:** 0.1.0 (daemon health check response)
- **Claude Code:** Latest (as of 2025-01-09)

### Relevant Files
- `CoDRAG/codrag-mcp-wrapper.sh` - MCP launcher
- `CoDRAG/.claude/mcp.json` - Claude Code MCP configuration
- `CoDRAG/src/codrag/mcp/server.py` - MCP server implementation
- `CoDRAG/src/codrag/mcp_server.py` - Entry point wrapper

### Process States Observed
```bash
# Initial (working)
ericbintner  7784  0.0  0.1  ...  S+  3:04PM  0:00.62 ... codrag mcp

# After failures (multiple orphans)
ericbintner  20648  0.0  0.1  ...  S  3:24PM  0:02.88 ... codrag mcp
ericbintner  20623  0.0  0.1  ...  S  3:24PM  0:01.95 ... codrag mcp
ericbintner   8474  0.0  0.1  ...  S  3:05PM  0:00.56 ... codrag mcp
```

Note: Multiple processes suggest either:
- Claude Code respawning on failure (good)
- Orphaned processes not cleaning up (bad)
- Need to verify PPID relationships

---

## Next Steps

1. **Immediate:** Add debug logging to MCP wrapper to capture next failure
2. **This Week:** Test `--mode direct` stability hypothesis
3. **Next Week:** Evaluate HTTP transport as development default
4. **Ongoing:** Document workarounds in team onboarding materials

---

*This document is a living research artifact. As new data is collected, hypotheses should be validated or rejected, and the workflow recommendations updated.*