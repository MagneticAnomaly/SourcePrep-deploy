## Debt Summary

| Metric | Value |
|--------|-------|
| **Total debt items** | 95 (68 explicitly classified + 27 additional findings) |
| **WARNING** | 29 items |
| **INFO** | 39 items |
| **Unclassified residual** | 27 items |
| **Structural anchor (spaghetti hotspots)** | 1 critical, 1 warning |
| **Estimated remediation** | 20–30 engineering days (~4–6 weeks) |

Severity is anchored in structural data: spaghetti analysis flags **1 critical** and **1 warning** hotspot, both in research documentation with extreme debt density. Static analysis layers on top of that baseline to produce the WARNING and INFO distributions above.

## Spaghetti Hotspots

**Module: unassigned (Research Documentation)**
- `docs/research/RESEARCH_BRIGHTNESS.md` — **Score 0.79 (critical)**. Dominant signal: **debt density in a large file** (755 LOC, 6 debt items, fan-in=1). The file is overweight with undocumented research fragments and contradictions.
- `docs/research/RESEARCH_AUDIO.md` — **Score 0.64 (warning)**. Dominant signal: **debt density in a large file** (639 LOC, 5 debt items, fan-in=1). Similar density problem with cross-document contradictions.

## By Module

### unassigned — WARNING, 11 items across 2 files
*Both files are spaghetti hotspots; all 11 items are concentrated here.*
- **`docs/research/RESEARCH_BRIGHTNESS.md`** (hotspot score 0.79, critical): 6 debt items. Research notes are duplicated, stale, and contradict `README.md` / `CODE_SIGNING.md`. **Effort:** 1 day to consolidate, deduplicate, and migrate into canonical docs.
- **`docs/research/RESEARCH_AUDIO.md`** (hotspot score 0.64, warning): 5 debt items. Contains neighbor-context contradictions between installation instructions and code-signing guidance. **Effort:** 1 day.

### PowerMate Hardware & Audio Volume Controller — WARNING, 8 items across 2 files
- **`Sources/PowerMateManager.swift`**: `Timer.scheduledTimer` callbacks mutate shared state (`buttonDownTime`, etc.) without synchronization, risking races and re-entrancy bugs. **Effort:** 2–3 days (refactor to `Combine`, `async`, or actor-isolated state).
- **`Sources/VolumeController.swift`**: Related timer-driven volume state mutations and callback logic. **Effort:** 1–2 days.

### Multi-Strategy Display Brightness Controller — WARNING, 5 items across 1 file
- **`Sources/BrightnessController.swift`**: `loadDisplayServices()` relies on private Apple APIs that may be removed or changed in any macOS update. No runtime fallback or weak-linking guard is present. **Effort:** 2–3 days (add capability probing + graceful degradation).

### macOS OSD HUD Overlay — WARNING, 5 items across 1 file
- **`Sources/OSDOverlay.swift`**: References `LevelBarView` and `OSDBackgroundView`, but their implementations are not visible in the module—indicating dead code, missing files, or incomplete feature stubs. **Effort:** 1–2 days (locate implementations or excise references).

### PowerMateReborn Project Documentation — INFO, 4 items across 1 file
- **`README.md`**: Installation section contains an outdated notarization warning ("Since the app is not yet notarized by Apple...") that contradicts `CODE_SIGNING.md`. **Effort:** 2 hours.

### Menu Bar Application Controller — INFO, 4 items across 1 file
- **`Sources/AppDelegate.swift`**: `coloredImage = img.copy() as! NSImage` uses a forced cast that will crash if `copy()` returns an unexpected type. **Effort:** 30 minutes.

### PowerMate Custom Mode Action Engine — INFO, 4 items across 1 file
- **`Sources/CustomModeEngine.swift`**: `CodableActionConfig` encodes all parameter fields unconditionally regardless of action type, bloating persisted JSON and risking deserialization mismatches. **Effort:** 3–4 hours.

### Apple Silicon DDC Monitor Controller — INFO, 4 items across 1 file
- **`Sources/DDCController.swift`**: `loadIOAVService()` dynamically resolves private IOKit I2C symbols (`IOAVServiceReadI2C` / `IOAVServiceWriteI2C`). Brittle across macOS versions and fails opaquely if symbols shift. **Effort:** 1–2 days (harden resolution + add fallback).

### OSC Network Message Sender — INFO, 4 items across 1 file
- **`Sources/OSCController.swift`**: `NWEndpoint.Port(rawValue: port)!` in `send(_:host:port:)` force-unwraps a failable initializer and will crash on invalid port input. **Effort:** 30 minutes.

### PowerMate BLE Transport — INFO, 4 items across 1 file
- **`Sources/PowerMateBLETransport.swift`**: `didDiscoverServices`