# Paperclip + Sequential Thinking MCP + Superpowers Ecosystem
## Problem
Paperclip is installed (`~/paperclip`) and operational with the `claude-local` adapter, but the two other ecosystem components — **Sequential Thinking MCP** (structured reasoning) and **Superpowers** (TDD/planning methodology) — are not yet installed or wired into the agent workflow.
## Current State
* **Paperclip**: Cloned at `~/paperclip`, config at `~/.paperclip/instances/`. Uses `@paperclipai/adapter-claude-local` to spawn Claude Code CLI as child processes for agents.
* **Claude Code CLI**: Installed at `~/.nvm/versions/node/v22.19.0/bin/claude`
* **MCP servers** (`~/.claude/settings.json`): blender, desktop-commander — no sequential-thinking
* **Superpowers**: Not installed (no plugins directory entries)
* **Sequential Thinking**: Not registered as MCP server
## Proposed Changes
### Step 1: Install Sequential Thinking MCP Server
Register the MCP server so all Claude Code sessions (including Paperclip-spawned agents) can use `sequential_thinking`.
Run via Claude Code CLI:
```warp-runnable-command
claude mcp add sequential-thinking --scope user -- npx -y @modelcontextprotocol/server-sequential-thinking
```
This adds it to `~/.claude/settings.json` at user scope, making it available to all sessions including those Paperclip spawns.
### Step 2: Install Superpowers Plugin in Claude Code
Superpowers is a Claude Code plugin installed from within a Claude Code session:
```warp-runnable-command
/plugin install superpowers@claude-plugins-official
```
This installs the skill set (brainstorming, writing-plans, TDD, subagent-driven-development, etc.) and the SessionStart hook that injects discipline into every session.
**Note**: The `claude-local` adapter in Paperclip passes `--add-dir` for its own skills but also inherits the user's global Claude Code plugins. Since Superpowers installs as a user-level plugin with hooks, Paperclip-spawned agents will pick it up automatically.
### Step 3: Verify MCP + Plugin Availability
After installing both, verify:
1. `claude mcp list` — should show `sequential-thinking` as active
2. Start a Claude Code session and run `/mcp` — should show sequential-thinking connected
3. Ask Claude: "List your available Superpowers skills" — should enumerate brainstorming, TDD, etc.
### Step 4: Configure Paperclip Agent Prompt to Use the Full Loop
Paperclip's `claude-local` adapter uses a `promptTemplate` and optionally a `bootstrapPromptTemplate` (see `execute.ts` lines 312-315, 391-405). The bootstrap prompt runs on the first session and the prompt template on every heartbeat.
To enforce the **Sequential Thinking → Superpowers** ordering, configure the agent's prompt template in the Paperclip UI (or via agent config) to include instructions like:
```warp-runnable-command
Before starting any implementation task:
1. Use the sequential_thinking MCP tool to break down the problem into structured reasoning steps
2. Once reasoning is complete, follow your Superpowers skills (brainstorming → writing-plans → TDD → subagent-driven-development)
3. Report progress back to Paperclip via your standard heartbeat
```
This is set per-agent in Paperclip's board UI under the agent's adapter configuration (`config.promptTemplate` or `config.bootstrapPromptTemplate`).
### Step 5: Start Paperclip Dev Server and Test End-to-End
1. Start Paperclip: `cd ~/paperclip && pnpm dev`
2. Create a company and hire a test agent with the claude-local adapter
3. Assign a small task (e.g., "Create a hello-world Express endpoint with tests")
4. Observe: Agent should invoke `sequential_thinking` for reasoning, then follow Superpowers TDD workflow
5. Verify in Paperclip dashboard: heartbeats, cost tracking, and activity logs
## Architecture Summary
```warp-runnable-command
Paperclip Board UI (Goal/Task) 
  → claude-local adapter spawns `claude` CLI
    → Claude Code session has:
      - Sequential Thinking MCP (user-scope, via ~/.claude/settings.json)
      - Superpowers plugin (user-scope, via ~/.claude/plugins/)
      - Paperclip skills (ephemeral, via --add-dir)
      - Agent prompt enforcing: sequential_thinking → superpowers workflow
    → Reports back heartbeats/cost to Paperclip API
```
