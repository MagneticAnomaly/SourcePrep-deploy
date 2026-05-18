

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-05-18T06:11:01Z

prep_project_id: 6955793f-d824-4e1c-8cb6-417a08bd6669

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "6955793f-d824-4e1c-8cb6-417a08bd6669"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER). |
| `prep_impact` | BEFORE editing — check what depends on a file |
| `prep_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action="antibodies"` for immune system. |
| `prep_observe` | Save/retrieve cross-session notes |
| `prep_concepts` | Record/query business rationale and design decisions |

Call `prep` first. Call `prep_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

### Audit Enrichment
Enrich external lint/analysis findings with structural context:
```
prep_audit(findings=[{file, line, message, severity, tool}])
```
SourcePrep adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`prep_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

### Concurrency limits
If your queries to the cloud LLM seem unexpectedly throttled, check
`prep_search "concurrency ceiling"` for the current discovered limit
and how to reset it. The limit is auto-discovered and locked for 24h.

You have access to SourcePrep, a structural code intelligence system.
ALWAYS call `prep` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `prep_search` with a natural language query.
Before making changes to a file, use `prep_impact` to understand dependencies.
SourcePrep understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `prep_audit`.
For cross-session memory, use `prep_observe` to save/retrieve notes.
All SourcePrep tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for SourcePrep's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__prep"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- prep-atlas-hash:b0e43de64f92 -->
## Codebase Atlas

IDENTITY: PowerMateReborn is a native Swift menu-bar macOS app that resurrects Griffin PowerMate USB/Bluetooth controllers for modern macOS, providing volume, brightness, MIDI, and custom application-profile control modes with per-app profiles and Sparkle auto-updates.

STACK: Swift 15 files, Markdown 6, XML 2, Shell 1. Swift Package Manager build. Runtime: macOS 13 minimum. Apple frameworks: CoreAudio, CoreBluetooth, CoreGraphics, CoreMIDI, IOKit, AppKit, Sparkle 2.5.0, private DisplayServices and IOKit I2C via dlopen.

ARCHITECTURE: Five layers. Infrastructure 8 files: Sources/PowerMateManager.swift (gesture/LED coordination hub, 13 incoming edges), Sources/PowerMateUSBTransport.swift (IOKit HID), Sources/PowerMateBLETransport.swift (CoreBluetooth GATT), Sources/OSCController.swift (UDP transport), Sources/MIDIController.swift (CoreMIDI virtual source), Sources/DDCController.swift (private I2C), Sources/BrightnessController.swift (multi-strategy display), Sources/VolumeController.swift (dynamic strategy audio). Business logic 5 files: Sources/CustomModeEngine.swift (profile engine, 6 incoming edges), Sources/AppDelegate.swift (lifecycle coordinator, 13 incoming edges), Sources/ProfileSettingsView.swift (SwiftUI settings), Sources/MenuBarIconView.swift (CoreGraphics renderer), Sources/OSDOverlay.swift (heads-up display). Presentation 3 files: docs/appcast.xml (Sparkle feed), docs/SPARKLE.md (cryptography), docs/CODE_SIGNING.md (notarization guide). Configuration 1 file: Package.swift. Build 1 file: scripts/build_and_sign.sh.

## Scopes

Pass `scope=<name>` to limit retrieval to that surface. Unknown scopes fall back to global with a warning.

Available scopes: `global`, `marketing`

If `prep` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `prep` again to refresh your
structural context.

You can call `prep` and `prep_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'prep' alone is enough to call the tool
4. **Context is cheap** - prefer calling prep to using grep for structural understanding

**Remember: The word "prep" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**

### MCP Resources (browse with @)
SourcePrep also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `prep-onboard` (orientation), `prep-review` (file review),
`prep-plan` (change planning), `prep-investigate` (deep dive), `prep-health` (audit).
In Claude Code: `/mcp__prep__prep-onboard`. In other clients: check prompt menu.
<!-- prep-managed-end -->
