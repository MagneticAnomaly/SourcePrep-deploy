## Gap Inventory

### GAP-1: Orphaned Core Modules / Broken Static Dependency Graph
- **Severity:** Critical
- **Affected Files:** `Sources/BrightnessController.swift`, `Sources/CustomModeEngine.swift`, `Sources/CustomModeSettingsView.swift`, `Sources/DDCController.swift`, `Sources/MIDIController.swift`, `Sources/MenuBarIcon.swift`, `Sources/OSCController.swift`, `Sources/OSDOverlay.swift`, `Sources/PowerMateBLETransport.swift`, `Sources/PowerMateUSBTransport.swift`, `Sources/VolumeController.swift`
- **Problem:** Eleven core/UI files report **zero incoming import edges** and are not classified as entry points, yet the module summaries treat them as active dependencies of the application coordinator (e.g., `display-control`, `midi-transport`, `hardware-event-coordinator`). This indicates either (a) the files are compiled into the binary but are unreachable dead code, (b) the build target is misconfigured in `Package.swift`, or (c) the project relies on unsafe runtime composition (e.g., string-based instantiation) that evades static analysis. The disconnect between the architectural dependency graph and the static import graph makes the codebase unmaintainable and suggests features like BLE, DDC, MIDI, and OSC may be shipping as inert binaries.
- **Resolution:** Audit `Package.swift` target source memberships. If the files are intended to be live, add explicit `import` relationships or register them in a startup factory. If they are dynamically loaded, replace runtime magic with a typed dependency-injection container. If they are truly unused, delete them to reduce attack surface and compile times.

### GAP-2: Circular Dependency — Application Lifecycle ↔ Profile Engine
- **Severity:** High
- **Affected Files:** `Sources/AppDelegate.swift`, `Sources/CustomModeEngine.swift`
- **Problem:** The module dependency graph shows a cycle: **Application Lifecycle & Hardware Input Coordinator** depends on `custom-mode-controller`, while **PowerMate Profile Engine** (`CustomModeEngine.swift`) depends on `application_coordination`. This tight coupling prevents independent testing, complicates initialization order, and encourages the AppDelegate to become a god-object.
- **Resolution:** Break the cycle by introducing a shared `Core/Protocols` module. Define a `ModeControlling` protocol consumed by `AppDelegate`, and an `AppLifecycleEvents` protocol (or an `AsyncSequence` event bus) consumed by `CustomModeEngine`. Do not let concrete modules depend on each other bidirectionally.

### GAP-3: Bootstrap/UI Module Cohesion Violation
- **Severity:** Medium
- **Affected Files:** `Sources/main.swift`, `Sources/CustomModeSettingsView.swift`
- **Problem:** The module *Menu-Bar App Bootstrap & Profile Settings UI* conflates two unrelated concerns: POSIX signal handling and application bootstrap (`main.swift`) with SwiftUI presentation logic (`CustomModeSettingsView.swift`). This forces the bootstrap layer to carry UI dependencies and makes the settings view difficult to import in isolation (e.g., for Previews or testing).
- **Resolution:** Physically split the files into two distinct modules: `Bootstrap` (`main.swift`, `AppDelegate.swift`) and `UI.Settings` (`CustomModeSettingsView.swift`). Update `Package.swift` so that `Bootstrap` does not depend on the UI module; instead, the UI should be lazily loaded by a coordinator via a factory closure.

### GAP-4: Unsafe Hardware Abstraction Layer (HAL)
- **Severity:** High
- **Affected Files:** `Sources/BrightnessController.swift`, `Sources/DDCController.swift`, `Sources/MIDIController.swift`, `Sources/OSCController.swift`
- **Problem:** High-level application logic is directly fused to unsafe low-level implementation details: `DDCController` dynamically loads private `IOKit` symbols; `OSCController` force-unwraps `NWEndpoint.Port(rawValue: port)!`; `MIDIController` uses fixed-size buffers with no thread safety; `BrightnessController` couples private API fragility with gamma-table capture. There is no defensive boundary or validation layer between hardware I/O and the rest of the app.
- **Resolution:** Introduce a `HardwareAbstraction` protocol layer (e.g., `DisplayControlling`, `MIDITransporting`, `OSCTransporting`). Move all private API calls, `dlsym` lookups, raw UDP socket construction, and fixed-buffer MIDI packet lists into isolated `*HardwareService` structs that conform to these protocols. Validate all inputs at the protocol boundary and return `Result` or `throws` instead of crashing.

### GAP-5: Misplaced Release Engineering Assets
- **Severity:** Medium
- **Affected Files:** `docs/appcast.xml`, `scripts/SPARKLE_SETUP.md`, `Package.swift`
- **Problem:** Release artifacts and documentation are treated as logical application modules in the architecture analysis. `Package.swift` declares a redundant Sparkle linkage (SPM product dependency *and* manual `.linkedFramework`), and the appcast XML contains a future-dated `pubDate` (`Thu, 12 Mar 2026`). Build concerns are leaking into the source dependency graph.
- **Resolution:** Move `docs/appcast.xml` and `scripts/SPARKLE_SETUP.md` to a top-level `Infrastructure/` or `.github/release/` directory outside `Sources/`. Remove the manual `.linkedFramework("Sparkle")` declaration from `Package.swift` if the SPM `.product(name: "Sparkle", ...)` dependency is already present.

### GAP-6: Missing Test Coverage / No Test Target
- **Severity:** High
- **Affected Files:** Entire project; especially `Sources/CustomModeEngine.swift`, `Sources/VolumeController.swift`, `Sources/DDCController.swift`
- **Problem:** No test modules, test targets, or test files appear in any findings or module summaries. With 27+ tech debt items spanning hardware protocols, memory bloat (`CodableActionConfig`), and private API fragility, the project has zero automated regression safety.
- **Resolution:** Add a `PowerMateRebornTests` target in `Package.swift`. Prioritize protocol-based mocking for `DDCController`, `MIDIController`, and `PowerMateTransport`. Write unit tests for `VolumeController` strategy selection and `CustomModeEngine` profile resolution.

### GAP-7: Implicit Singletons and Global State
- **Severity:** Medium
- **Affected Files:** `Sources/MIDIController.swift`, `Sources/AppDelegate.swift`
- **Problem:** `MIDIController` contains an implicit singleton (tech debt item: `implicit-singl`). The module summaries show many modules depending on `application_coordination`, indicating `AppDelegate` is acting as a global service locator. This makes parallel testing impossible and hides transitive dependencies.
- **Resolution:** Refactor `MIDIController` into an explicit actor or struct initialized with a `MIDIDestination` configuration. Refactor `AppDelegate` into discrete, stateless services (`EventRouter`, `TransportManager`, `ModeCoordinator`) wired together in `main.swift` by a composition root.

### GAP-8: Incomplete Bluetooth Integration
- **Severity:** Medium
- **Affected Files:** `Sources/PowerMateBLETransport.swift`, `README.md`
- **Problem:** The README marks Bluetooth support as Beta with "real-hardware validation incomplete." Simultaneously, `PowerMateBLETransport.swift` is an orphaned module with no static imports. The feature appears half-built and untested, yet it is compiled into the product.
- **Resolution:** Gate `PowerMateBLETransport` behind a compile-time or runtime feature flag (e.g., `#if ENABLE_BLE_TRANSPORT`). Complete hardware validation with the orphaned module explicitly imported into a `TransportFactory`, or remove it from the release target until it is wired and tested.

### GAP-9: Data Model Bloat in Profile Engine
- **Severity:** Medium
- **Affected Files:** `Sources/CustomModeEngine.swift`
- **Problem:** `CodableActionConfig` is a massive struct containing unused fields for every action type, causing memory bloat. This is a classic "god object" anti-pattern in data modeling, likely arising from a flattened schema designed for `Codable` convenience rather than type safety.
- **Resolution:** Replace the monolithic struct with a Swift enum using associated values (e.g., `ActionConfiguration.keyboard(KeyboardAction)`, `.midi(MIDIAction)`, `.osc(OSCAction)`). Implement custom `Encodable`/`Decodable` conformance to preserve backward compatibility with existing JSON profiles while eliminating unused field memory overhead.

### GAP-10: UI Icon Responsibility Leakage
- **Severity:** Low
- **Affected Files:** `Sources/AppDelegate.swift`, `Sources/MenuBarIcon.swift`
- **Problem:** `MenuBarIcon.custom()` is reused as a placeholder for both MIDI and custom modes inside `AppDelegate`. The module summary shows *Menu Bar Icon Renderer* depends on `application_coordination`, which is an inverted dependency: a pure UI rendering utility should not depend on the application coordinator.
- **Resolution:** Invert the dependency. Define a `MenuBarIconProviding` protocol in the coordinator module. `AppDelegate` should request an icon from the provider based on the current mode. `MenuBarIcon.swift` should become a pure CoreGraphics rendering utility with zero knowledge of application state.

### GAP-11: Strategy Conflation in Brightness Controller
- **Severity:** Medium
- **Affected Files:** `Sources/BrightnessController.swift`
- **Problem:** A single file/module implements five disparate brightness strategies (private `DisplayServices`, DDC/CI, hybrid DDC+gamma, pure gamma, AppleScript). This violates the Single Responsibility Principle and causes the fragility of private APIs to contaminate the entire brightness subsystem.
- **Resolution:** Extract a `BrightnessStrategy` protocol with a single method `setBrightness(_:forDisplay:)`. Create separate implementations: `DisplayServicesBrightnessStrategy`, `DDC