## Gap Inventory

**GAP-1: Orphaned Hardware & Media Controller Layer**
- **Severity:** Critical
- **Affected Files:** `Sources/PowerMateUSBTransport.swift`, `Sources/PowerMateBLETransport.swift`, `Sources/VolumeController.swift`, `Sources/BrightnessController.swift`, `Sources/DDCController.swift`, `Sources/MIDIController.swift`, `Sources/OSCController.swift`
- **Problem Description:** Seven core controllers and hardware transports have zero incoming import edges and are not classified as entry points. The application bootstrap (`AppDelegate.swift`) does not statically reference the transport layer, media bridges (MIDI/OSC), or display controllers, meaning the advertised USB/BLE, audio volume, brightness, and external-control capabilities are either dead code or wired through opaque runtime composition that evades compile-time linking and module boundaries.
- **Resolution:** Introduce a `CompositionRoot.swift` (or explicitly wire inside `AppDelegate.swift`) that instantiates and retains these controllers. Inject them via protocol into `PowerMateManager` and the menu-bar lifecycle. If runtime composition is intentional, replace it with explicit factory registration so static analysis and the compiler can verify the graph.

**GAP-2: Orphaned Feedback & Configuration UI Layer**
- **Severity:** Critical
- **Affected Files:** `Sources/OSDOverlay.swift`, `Sources/MenuBarIcon.swift`, `Sources/CustomModeSettingsView.swift`
- **Problem Description:** The on-screen display HUD, menu-bar vector icon renderer, and custom-mode settings UI are modular islands with no consumers. Native UX capabilities exist as source files but are never presented or retained by the application lifecycle, making the user-facing configuration surface unreachable.
- **Resolution:** Integrate `OSDOverlay` and `MenuBarIcon` into a `StatusBarController` owned by `AppDelegate`. Present `CustomModeSettingsView` through a dedicated coordinator that bridges the view and the engine.

**GAP-3: Fractured Custom Mode Vertical Slice**
- **Severity:** High
- **Affected Files:** `Sources/CustomModeEngine.swift`, `Sources/CustomModeSettingsView.swift`
- **Problem Description:** The action engine and its configuration UI are both orphaned and show no static import edge in either direction. The module summary claims the UI “drives the CustomModeEngine” and the engine handles profile management, yet the dependency graph shows a broken vertical slice. Profiles cannot be configured if the UI cannot call the engine, and the engine cannot be triggered if no coordinator dispatches to it.
- **Resolution:** Create a `CustomModeCoordinator` (or extend `PowerMateManager`) that imports both the engine and the settings view, mediating profile CRUD and action dispatch with explicit, typed references.

**GAP-4: Missing Transport Abstraction**
- **Severity:** High
- **Affected Files:** `Sources/PowerMateManager.swift`, `Sources/PowerMateUSBTransport.swift`, `Sources/PowerMateBLETransport.swift`
- **Problem Description:** Both USB and BLE transports are orphaned, yet `PowerMateManager` (which is linked) is described as mediating gesture input across “all transports.” There is no visible `PowerMateTransport` protocol or factory, and the manager does not appear to import either transport statically. This implies either duplicated transport logic inside the manager, runtime discovery that bypasses type safety, or a missing abstraction.
- **Resolution:** Define a `PowerMateTransport` protocol in a shared contract file. Have `PowerMateManager` depend on an array of `any PowerMateTransport`. Make both concrete transports conform and register them via an explicit factory that `PowerMateManager` consumes on initialization.

**GAP-5: Unsafe Bootstrap Cast & Signal Handler Fragility**
- **Severity:** High
- **Affected Files:** `Sources/AppDelegate.swift`
- **Problem Description:** `AppDelegate.swift` contains an unsafe forced cast (`coloredImage = img.copy() as! NSImage`) that will crash at runtime if `copy()` returns an incompatible type. Additionally, the module summary notes POSIX signal handlers for gamma restoration on termination, but `BrightnessController` (which handles display restoration) is orphaned, suggesting the signal handler may reference a non-existent or uninitialized controller.
- **Resolution:** Replace `as!` with `guard let coloredImage = img.copy() as? NSImage else { return fallback }`. Ensure `AppDelegate` holds a strong reference to a display-brightness controller *before* installing `SIGINT`/`SIGTERM` handlers that rely on it.

**GAP-6: Private API Entrenchment Without Isolation**
- **Severity:** High
- **Affected Files:** `Sources/BrightnessController.swift`, `Sources/DDCController.swift`
- **Problem Description:** Both files dynamically resolve or directly call private IOKit symbols (`IOAVServiceReadI2C`, `IOAVServiceWriteI2C`, `loadDisplayServices`). These private APIs are scattered across concrete controllers rather than isolated behind an adapter. If Apple removes or renames these symbols, the crash surface spans multiple modules and there is no compile-time or runtime fallback.
- **Resolution:** Extract all private API calls into a single `PrivateDisplayServices` adapter with a stable protocol interface. Implement a public-API fallback strategy (e.g., CoreDisplay or software gamma) so `BrightnessController` and `DDCController` depend only on the stable abstraction.

**GAP-7: Hardcoded MIDI Buffer & OSC Connection Cache Leaks**
- **Severity:** Medium
- **Affected Files:** `Sources/MIDIController.swift`, `Sources/OSCController.swift`
- **Problem Description:** `MIDIController` hardcodes `MIDIPacketList` size parameters, risking buffer overflow on larger messages. `OSCController` caches persistent UDP connections per host:port, but there is no evidence of lifecycle teardown, cache eviction, or connection invalidation on app termination, leading to file-descriptor and memory leaks.
- **Resolution:** Replace hardcoded MIDI sizes with `MemoryLayout`–based calculations or dynamically sized buffers. Add a connection pool with TTL/expiry in `OSCController` and ensure `deinit` or app-termination invalidates all cached `NWConnection` objects.

**GAP-8: Inefficient Action Serialization & Fragile UI Assumptions**
- **Severity:** Medium
- **Affected Files:** `Sources/CustomModeEngine.swift`, `Sources/CustomModeSettingsView.swift`
- **Problem Description:** `CodableActionConfig` encodes all parameter fields regardless of action type, bloating the persistence payload with irrelevant data. `CustomModeSettingsView` assumes `engine.profiles.last` is the newly added profile, which breaks if the engine ever sorts, filters, or inserts profiles non-append-only.
- **Resolution:** Refactor `CodableActionConfig` into a discriminated enum with associated values so only relevant parameters are encoded. Replace index/assumption-based profile selection with an ID returned by the engine on `addProfile()`.

**GAP-9: Documentation & Build Configuration Drift**
- **Severity:** Medium
- **Affected Files:** `docs/research/RESEARCH_AUDIO.md`, `docs/research/RESEARCH_BRIGHTNESS.md`, `README.md`, `Package.swift`
- **Problem Description:** Research markdown files are categorized under an `unassigned` module carrying 11 tech-debt items, indicating the project boundary and module mapping are misconfigured. `README.md` contradicts `CODE_SIGNING.md` on installation requirements. `Package.swift` pins Sparkle to an open minor-version floor (`from: "2.5.0"`) without an upper bound, risking unexpected breaking changes on fresh resolves.
- **Resolution:** Exclude `docs/` from code-module analysis and package manifests. Reconcile `README.md` and `CODE_SIGNING.md` instructions. Pin Sparkle to an exact patch version or a closed semantic range (e.g., `"2.5.0"..<"2.6.0"`).

**GAP-10: Timer-Based State Mutation Debt in PowerMateManager**
- **Severity:** Medium
- **Affected Files:** `Sources/PowerMateManager.swift`, `Sources/VolumeController.swift`
- **Problem Description:** The module carries 8 tech-debt items around `Timer.scheduledTimer` callbacks and manual state mutations (`buttonDownTime`). This indicates ad-hoc timer management rather than a structured gesture-state machine, leading to race conditions, retain cycles, and undefined behavior during rapid knob rotation or button presses.
- **Resolution:** Replace manual `Timer` callbacks with a `Combine` pipeline or a formal `GKStateMachine` for gesture recognition. Ensure all timers are invalidated on transport disconnect and `deinit`.

## Priority Ranking

| Gap ID | Severity | Effort | Priority |
|---|---|---|---|
| GAP-1 | Critical | High | P0 |
| GAP-2 | Critical | Medium | P0 |
| GAP-5 | High | Low | P0 |
| GAP-3 | High | Medium | P1 |
| GAP-4 | High | Medium | P1 |
| GAP-6 | High | High | P1 |
| GAP-7 | Medium | Low | P2 |
| GAP-8 | Medium | Low | P2 |
| GAP-10 | Medium | Medium | P2 |
| GAP-9 | Medium | Low | P3 |

## Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CURRENT (BROKEN) DEPENDENCY GRAPH                  │
└─────────────────────────────────────────────────────────────────────┘

AppDelegate.swift
    │
    ├─► PowerMateManager.swift ............................... [linked]
    │
    ├─╳ PowerMateUSBTransport.swift ......................... [orphan]
    ├─╳ PowerMateBLETransport.swift ......................... [orphan]
    ├─╳ VolumeController.swift .............................. [orphan]
    │
    ├─╳ BrightnessController.swift .......................... [orphan]
    │       └─╳ DDCController.swift ........................... [orphan]
    │
    ├─╳ MIDIController.swift .................................. [orphan]
    ├─╳ OSCController.swift ................................. [orphan]
    │
    ├─╳ CustomModeEngine.swift ............................... [orphan]
    │       └─╳ CustomModeSettingsView.swift .................. [orphan]
    │
    ├─╳ OSDOverlay.swift .................................... [orphan]
    └─╳ MenuBarIcon.swift ................................... [orphan]

┌─────────────────────────────────────────────────────────────────────┐
│                  INTENDED (MISSING) WIRING                            │
└─────────────────────────────────────────────────────────────────────┘

AppDelegate.swift
    │
    ├─► PowerMateManager.swift
    │       ├─► PowerMateTransport (protocol) ◄──┐
    │       │       ├─► PowerMateUSBTransport.swift
    │       │       └─► PowerMateBLETransport.swift
    │       └─► VolumeController.swift
    │
    ├─► BrightnessController.swift
    │       └─► DDCController.swift
    │
    ├─► MIDIController.swift
    ├─► OSCController.swift
    │
    ├─► CustomModeCoordinator (missing abstraction)
    │       ├─► CustomModeEngine.swift
    │       └─► CustomModeSettingsView.swift
    │
    ├─► OSDOverlay.swift
    └─► MenuBarIcon.swift