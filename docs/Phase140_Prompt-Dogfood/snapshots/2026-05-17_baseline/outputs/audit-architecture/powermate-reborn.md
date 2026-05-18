## Architecture Overview

PowerMateReborn is a native Swift macOS menu-bar application that resurrects Griffin PowerMate USB/Bluetooth controllers. Logically, the system organizes into four horizontal runtime tiers plus a build/distribution plane:

1. **Hardware & Transport** — USB HID (`Griffin PowerMate USB HID Transport`), Bluetooth LE (`PowerMate BLE Transport Driver`), DDC/CI (`DDC/CI Hardware Controller`), and protocol bridges (`Virtual MIDI Source Controller`, `OSC UDP Transport Controller`).
2. **Control & Effects** — Domain-specific actors for audio (`macOS Audio Volume Controller`), display brightness (`Multi-Strategy Display Brightness Controller`), and profile execution (`PowerMate Profile Engine`, `custom-mode-controller`).
3. **Application Core** — Lifecycle management, hardware event routing, gesture recognition (`PowerMate Gesture & LED Coordinator`), and settings persistence.
4. **Presentation** — SwiftUI settings UI (`Menu-Bar App Bootstrap & Profile Settings UI`), menu-bar icons (`Menu Bar Icon Renderer`), and OSD overlays (`macOS OSD Overlay Renderer`).
5. **Build & Distribution** — SPM manifest, DMG orchestration, Sparkle appcast generation, and documentation.

Despite this logical layering, the physical dependency graph collapses into a centralized star topology anchored by a single application coordinator.

---

## Module Dependency Flow

The dependency graph is heavily centralized. The module identity `application_coordination` (physically realized in `Sources/AppDelegate.swift`) is a mandatory dependency for UI components, hardware drivers, audio/display controllers, and even build infrastructure.

**Key dependency channels:**
- **`application_coordination`** → imported by `Menu-Bar App Bootstrap`, `Menu Bar Icon Renderer`, `macOS OSD Overlay Renderer`, `macOS Audio Volume Controller`, `PowerMate Profile Engine`, `OSC UDP Transport Controller`, `PowerMate BLE Transport Driver`, `Swift Package Manager Build Manifest`, `Virtual MIDI Source Controller`, `Multi-Strategy Display Brightness Controller`, `Griffin PowerMate USB HID Transport`, and `PowerMate Gesture & LED Coordinator`.
- **`hardware-event-coordinator`** → imported by both high-level controllers (`macOS Audio Volume Controller`, `Multi-Strategy Display Brightness Controller`, `PowerMate Profile Engine`) and low-level transports (`PowerMate BLE Transport Driver`, `Griffin PowerMate USB HID Transport`), placing it ambiguously between layers.
- **`custom-mode-controller`** → imported by `Application Lifecycle & Hardware Input Coordinator`, `Menu-Bar App Bootstrap`, `macOS Audio Volume Controller`, `OSC UDP Transport Controller`, `Virtual MIDI Source Controller`, and `PowerMate Gesture & LED Coordinator`.

**Concerning patterns:**
- **Star topology / God module**: `Sources/AppDelegate.swift` is imported by 13 files (mean=2.7, z-score=3.7), making it a mandatory transit point for nearly every feature.
- **Inverted hardware dependency**: `DDC/CI Hardware Controller` depends on `display-control` (the multi-strategy brightness policy module), meaning a low-level I2C driver imports high-level domain logic.
- **Concrete transport leakage**: `PowerMate Gesture & LED Coordinator` directly imports `usb-hardware-transport` and `hardware_transport` rather than an abstract event stream.
- **Build/runtime entanglement**: `Swift Package Manager Build Manifest` imports `application_coordination`, while `Application Lifecycle & Hardware Input Coordinator` imports `build-and-distribution`. These edges violate the boundary between compile-time configuration and runtime logic.

---

## Structural Bottlenecks

### Primary Hub
- **`Sources/AppDelegate.swift`** (in-degree: 13, z-score: 3.7)
  - **Role**: Main application delegate and coordinator that manages the application lifecycle and user settings persistence.
  - **Blast radius**: Changes to this file risk regression across UI rendering, hardware transport, audio/display control, MIDI/OSC integration, and build tooling. It is the single largest source of coupling in the codebase.

### Secondary Hubs
- **`custom-mode-controller`** — Imported by 6 modules. Acts as a secondary nexus for extensibility logic; changes to mode dispatch propagate through the application core, audio pipeline, and transport layers.
- **`display-control`** — Imported by 5–6 modules, including an inverted dependency from `DDC/CI Hardware Controller`.
- **`hardware-event-coordinator`** — Imported by 5 modules, creating tight coupling between physical hardware transports and high-level effect controllers.

---

## Boundary Violations

1. **Runtime → Build**  
   `Application Lifecycle & Hardware Input Coordinator` declares a dependency on `build-and-distribution`. Release engineering metadata should not be visible to runtime lifecycle logic.

2. **Build → Runtime**  
   `Swift Package Manager Build Manifest` declares a dependency on `application_coordination`. The package manifest must remain agnostic to application source semantics.

3. **Hardware → Policy**  
   `DDC/CI Hardware Controller` depends on `display-control`. The low-level DDC/CI I2C driver should be a leaf dependency consumed by `Multi-Strategy Display Brightness Controller`, not the reverse.

4. **Transport → Application Core**  
   `Griffin PowerMate USB HID Transport` and `PowerMate BLE Transport Driver` both depend on `application-coordination` / `application_coordination`. Hardware drivers should emit events upward via protocols rather than importing the main coordinator.

5. **Core → Concrete Hardware**  
   `PowerMate Gesture & LED Coordinator` depends on concrete `usb-hardware-transport` and `hardware_transport`. The gesture recognizer should be decoupled from specific BLE and USB transport implementations.

---

## Recommendations

### 1. Extract interfaces from `Sources/AppDelegate.swift`
Split `Sources/AppDelegate.swift` into role-specific protocols (e.g., `LifecycleCoordinating`, `SettingsPersisting`, `HardwareEventRouting`) placed in a new `Sources/Core/Interfaces/` directory. Refactor all 13 dependent modules to import only these protocols. Retain the concrete implementation in `Sources/AppDelegate.swift`, but restrict its direct visibility to the composition root. This eliminates the god-object bottleneck.

### 2. Invert the DDC/CI dependency
Remove the `display-control` dependency from `DDC/CI Hardware Controller`. Introduce a `DisplayHardwareControlling` protocol in a hardware-facing interface module, and make `Multi-Strategy Display Brightness Controller` depend on `DDC/CI Hardware Controller` via that protocol. This restores the correct direction: policy → hardware.

### 3. Decouple hardware transports from the application core
In `Griffin PowerMate USB HID Transport` and `PowerMate BLE Transport Driver`, remove imports of `application_coordination`. Define a `HardwareEventSink` protocol that transports call when input reports arrive. Inject the concrete coordinator (conforming to `HardwareEventSink`) at initialization from `Sources/AppDelegate.swift` or a dedicated assembly module.

### 4. Eliminate build/runtime cross-imports
- Remove `build-and-distribution` from the dependencies of `Application Lifecycle & Hardware Input Coordinator`. If build metadata is needed at runtime, read `Bundle.main.infoDictionary` or inject a `BuildMetadata` value type.
- Remove `application_coordination` from `Swift Package Manager Build Manifest`. If the manifest requires source awareness, use SPM build plugins or separate tool targets rather than importing application modules.

### 5. Abstract transport dependencies in gesture recognition
Refactor `PowerMate Gesture & LED Coordinator` to remove direct dependencies on `usb-hardware-transport` and `hardware_transport`. Depend on an abstract `HardwareTransport` protocol or solely on `HardwareEventCoordinator`. The coordinator should multiplex events from all attached transports so the gesture engine remains transport-agnostic.

### 6. Separate visual feedback from effect controllers
Remove `visual-feedback` dependencies from `macOS Audio Volume Controller` and `Multi-Strategy Display Brightness Controller`. Have controllers publish state changes via `NotificationCenter`, Combine publishers, or delegate protocols. Let `macOS OSD Overlay Renderer` or a new `FeedbackCoordinator` subscribe to these changes and render overlays, breaking the direct coupling between volume/brightness logic and UI presentation.