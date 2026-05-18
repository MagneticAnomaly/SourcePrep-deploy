## Health Score

**C+** — Zero critical findings keep the project shipping, but 9 warnings, 3 spaghetti hotspots (max score 0.68), and a hub bottleneck in `Sources/AppDelegate.swift` (in-degree 13, z-score 3.7) signal significant structural debt across core Swift files.

## Critical Findings

None. The audit surfaced **0 critical findings** out of 50 total.

## Top Recommendations

1. **Audit or remove 11 potentially unused Swift core files** — `Sources/BrightnessController.swift`, `Sources/VolumeController.swift`, `Sources/DDCController.swift`, `Sources/MIDIController.swift`, `Sources/OSCController.swift`, `Sources/PowerMateUSBTransport.swift`, `Sources/PowerMateBLETransport.swift`, `Sources/CustomModeEngine.swift`, `Sources/OSDOverlay.swift`, `Sources/MenuBarIcon.swift`, and `Sources/CustomModeSettingsView.swift` are flagged as having no import edges and no entry-point role. Verify whether they are dead code or dynamically loaded, then delete or properly wire them up to reduce the active codebase surface area.
2. **Decouple `Sources/AppDelegate.swift`** — With 13 incoming edges against a mean of 2.7 (z-score 3.7), it is the dominant hub bottleneck. Extract a protocol-based coordinator or split lifecycle responsibilities into dedicated services to lower coupling.
3. **Remediate core infrastructure tech debt** — `Sources/BrightnessController.swift` carries 7 debt items (private-api-dependency-fragility, no-sandbox-compliance, gamma-table-capture-ra) and `Sources/CustomModeEngine.swift` carries 5 debt items (massive `CodableActionConfig` struct causing memory bloat). Prioritize sandbox compliance and struct refactoring to stabilize the brightness and profile engines.
4. **Fix Sparkle auto-update metadata and build config** — Correct the future-dated `pubDate` (`Thu, 12 Mar 2026`) in `docs/appcast.xml`, review the 7 debt items in `scripts/SPARKLE_SETUP.md`, and remove the redundant Sparkle linkage in `Package.swift`.
5. **Consolidate research documentation spaghetti** — `docs/research/RESEARCH_BRIGHTNESS.md` (spaghetti score 0.68, ~755 lines, 3 debt items) and `docs/research/RESEARCH_AUDIO.md` (score 0.52, ~639 lines) are the top structural hotspots. Archive or distill these files to reduce cognitive load.

## Module Status

- **Menu-Bar App Bootstrap & Profile Settings UI** (2 files) — healthy — 3 tech debt items (`CodableAppProfile` memory inefficiency in `Sources/CustomModeSettingsView.swift` / `Sources/main.swift`).
- **Sparkle Auto-Update Feed & Release Cryptography** (2 files) — warning — 7 tech debt items; future-dated `pubDate` in `docs/appcast.xml`.
- **Swift Package Manager Build Manifest** (1 file) — healthy — redundant Sparkle linkage in `Package.swift`.
- **PowerMateReborn Application Documentation** (1 file) — warning — 5 tech debt items; incomplete Bluetooth hardware validation noted in `README.md`.
- **Application Lifecycle & Hardware Input Coordinator** (1 file) — warning — hub bottleneck (`Sources/AppDelegate.swift` in-degree 13, z-score 3.7) plus placeholder icon reuse tech debt.
- **Multi-Strategy Display Brightness Controller** (1 file) — warning — 7 tech debt items in `Sources/BrightnessController.swift` (private API fragility, sandbox compliance, gamma table capture).
- **PowerMate Profile Engine** (1 file) — warning — 5 tech debt items in `Sources/CustomModeEngine.swift` (`CodableActionConfig` memory bloat).
- **DDC/CI Hardware Controller** (1 file) — healthy — 3 tech debt items in `Sources/DDCController.swift` (dynamic private IOKit symbol loading).

## Next Steps

1. **Run a dead-code pass** on the 11 flagged Swift files to confirm whether `Sources/BrightnessController.swift`, `Sources/VolumeController.swift`, `Sources/DDCController.swift`, `Sources/MIDIController.swift`, `Sources/OSCController.swift`, `Sources/PowerMateUSBTransport.swift`, `Sources/PowerMateBLETransport.swift`, `Sources/CustomModeEngine.swift`, `Sources/OSDOverlay.swift`, `Sources/MenuBarIcon.swift`, and `Sources/CustomModeSettingsView.swift` are truly unreferenced; remove any confirmed dead code before the next release.
2. **Extract an interface from `Sources/AppDelegate.swift`** to break its 13 incoming dependencies and redistribute lifecycle coordination to smaller, single-responsibility types.
3. **Update the Sparkle feed metadata** by fixing the future-dated `pubDate` in `docs/appcast.xml` and deduplicating the Sparkle framework declaration in `Package.swift`.