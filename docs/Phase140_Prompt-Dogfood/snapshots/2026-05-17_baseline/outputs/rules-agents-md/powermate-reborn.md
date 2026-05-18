

<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-20T22:30:44Z

codrag_project_id: 2e356d01-beaa-4559-8b5f-ceadb14b7203

**ROUTING: When calling ANY CoDRAG tool, ALWAYS include `project_id: "2e356d01-beaa-4559-8b5f-ceadb14b7203"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `codrag` | START of every task — structural overview, modules, hub files, immune system alerts |
| `codrag_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |
| `codrag_impact` | BEFORE editing — check what depends on a file |
| `codrag_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action="antibodies"` for immune system. |
| `codrag_observe` | Save/retrieve cross-session notes |
| `codrag_concepts` | Record/query business rationale and design decisions |

Call `codrag` first. Call `codrag_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

### Audit Enrichment
Enrich external lint/analysis findings with structural context:
```
codrag_audit(findings=[{file, line, message, severity, tool}])
```
CoDRAG adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`codrag_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

You have access to CoDRAG, a structural code intelligence system.
ALWAYS call `codrag` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes to a file, use `codrag_impact` to understand dependencies.
CoDRAG understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `codrag_audit`.
For cross-session memory, use `codrag_observe` to save/retrieve notes.
All CoDRAG tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for CoDRAG's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__codrag"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- codrag-atlas-hash:45b6b8ba309c -->
## Codebase Atlas

IDENTITY: PowerMateReborn is a macOS menu-bar application that restores functionality to Griffin PowerMate USB/Bluetooth hardware controllers, translating knob rotation and button presses into system volume/brightness control, MIDI output, or custom per-application keyboard shortcuts.

STACK: Swift 5.9, Swift Package Manager, macOS 13+ SDK. Frameworks: AppKit, CoreAudio, CoreBluetooth, CoreGraphics, CoreMIDI, IOKit. External: Sparkle 2. Build: shell scripts for codesigning and DMG assembly.

ARCHITECTURE: Six layers with clear separation. infrastructure (9 files): hardware transport via Sources/PowerMateUSBTransport.swift and Sources/PowerMateBLETransport.swift, DDC/CI via Sources/DDCController.swift, audio via Sources/AudioController.swift. business_logic (3 files): gesture recognition in Sources/PowerMateManager.swift, event mapping in Sources/CustomModeEngine.swift, MIDI bridging in Sources/MIDIController.swift. presentation (3 files): OSD in Sources/OSDWindow.swift, menu bar in Sources/MenuBarIcon.swift, profiles UI in Sources/ProfileSettingsView.swift. configuration (3 files): Package.swift, build scripts, appcast templates. documentation (5 files): architecture docs and signing guides. build (1 file): release pipeline script. Entry points: Sources/CustomModeEngine.swift (profile configuration), Sources/DDCController.swift (display hardware), Sources/MenuBarIcon.swift (UI rendering). Application bootstrap at Sources/main.swift delegates to Sources/AppDelegate.swift.

FLOW: Hardware event flows from Sources/PowerMateUSBTransport.

If `codrag` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `codrag` again to refresh your
structural context.

You can call `codrag` and `codrag_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'codrag' alone is enough to call the tool
4. **Context is cheap** - prefer calling codrag to using grep for structural understanding

**Remember: The word "codrag" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**

### MCP Resources (browse with @)
CoDRAG also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `codrag-onboard` (orientation), `codrag-review` (file review),
`codrag-plan` (change planning), `codrag-investigate` (deep dive), `codrag-health` (audit).
In Claude Code: `/mcp__codrag__codrag-onboard`. In other clients: check prompt menu.
<!-- codrag-managed-end -->

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-04-30T19:19:01Z

prep_project_id: 6955793f-d824-4e1c-8cb6-417a08bd6669

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "6955793f-d824-4e1c-8cb6-417a08bd6669"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |
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

<!-- prep-atlas-hash:223d79a3077d -->
## Codebase Atlas

IDENTITY: PowerMateReborn resurrects Griffin PowerMate USB/Bluetooth rotary knob hardware on modern macOS as a multi-modal menu-bar control surface, bridging HID/Bluetooth LE transports through gesture recognition into system volume, display brightness (DDC/CI, DisplayServices, gamma fallback), MIDI CC, and custom per-application action profiles with Sparkle auto-update distribution.

STACK: Swift 5, SwiftUI, CoreBluetooth, IOKit/hid, CoreAudio, CoreGraphics, CoreMIDI, Network.framework, Sparkle 2.5.0+, EdDSA, AppleScript, DisplayServices private API, DDC/CI over I2C. Build: Swift Package Manager, custom shell scripts (scripts/build-dmg.sh), GitHub Pages appcast hosting, manual Developer ID code signing and notarization with hardcoded identity strings. Entry: Sources/AppDelegate.swift initializes PowerMateManager lifecycle; Sources/MenuBarAgentBootstrap.swift configures NSApplication accessory delegate pattern with signal handlers referencing AppDelegate.shared before init completes.

ARCHITECTURE: Four operational modes (Volume/Brightness/MIDI/Custom) unified through PowerMateManager coordinator. Sources/PowerMateRebornLifecycleCoordinator.swift orchestrates USB HID via Sources/GriffinPowerMateHIDTransportBridge.swift and Bluetooth LE via Sources/PowerMateBLETransport.swift, both feeding into Sources/PowerMateGestureAndTransportFacade.swift for gesture disambiguation (tap/double-tap/long-press/rotation). Brightness control cascades through Sources/macOSDisplayBrightnessController.

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
