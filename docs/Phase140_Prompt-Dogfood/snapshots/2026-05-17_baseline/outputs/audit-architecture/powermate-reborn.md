# PowerMateReborn Architecture Analysis

## Architecture Overview

The **PowerMateReborn** codebase is structured as a modular macOS menu-bar application designed to resurrect Griffin PowerMate hardware functionality. The architecture follows a **Layered Hexagonal** pattern, centering around a core orchestration layer that bridges low-level hardware transports (USB HID, BLE) with high-level system actions (Audio, Display, MIDI, OSC).

The system is organized into four distinct logical layers:
1.  **Infrastructure & Build**: Handles packaging, signing (Sparkle), and distribution pipelines.
2.  **Hardware Abstraction Layer (HAL)**: Manages physical transport (USB/BLE) and protocol decoding.
3.  **Core Orchestration**: The central nervous system (`PowerMateReborn Lifecycle Coordinator`) that routes events and manages application state.
4.  **Action & UI Layer**: Executes specific system commands (Volume, Brightness) and renders user interfaces (Menu Bar, HUD, Settings).

Notably, the project relies heavily on **fallback strategies** (documented in stubbed modules) to ensure compatibility across diverse macOS hardware configurations, particularly for Audio and Display control.

## Module Dependency Flow

The dependency graph reveals a strong centralization around the **Core Orchestration** concept.

*   **Upstream Flow (Hardware → Core)**:
    *   `Griffin PowerMate HID Transport Bridge` and `PowerMate BLE GATT Transport` both depend on `hardware-abstraction-core` and `core-orchestration`. They feed raw input events into the central coordinator.
    *   `PowerMate Gesture & Transport Facade` acts as a unifying layer, depending on `device_transport` and `core-orchestration`.

*   **Downstream Flow (Core → Actions/UI)**:
    *   The `PowerMateReborn Lifecycle Coordinator` acts as the primary hub, depending on `display-control`, `input-processing`, `custom-mode-configuration`, and `user_interface`.
    *   Specific action modules like `macOS Audio Volume Controller` and `macOS DisplayServices Brightness Controller` depend on `core-orchestration` to receive triggers, while also relying on `build-and-distribution` (likely for configuration constants or feature flags).

*   **Build & Distribution Coupling**:
    *   A significant portion of the runtime modules (e.g., `PowerMate BLE GATT Transport`, `macOS Audio Volume Controller`, `DDC/CI I2C Display Command Bridge`) explicitly list `build-and-distribution` as a dependency. This suggests that build-time configuration or environment-specific constants are being imported directly into runtime logic.

**Concerning Pattern**: The dependency direction between **Runtime Logic** and **Build Infrastructure** is inverted. Runtime modules should not depend on build pipelines.

## Structural Bottlenecks

While no single file has a calculated "in-degree" in the provided data, the conceptual module **`core-orchestration`** is the definitive architectural bottleneck.

*   **Identified Hub**: `PowerMateReborn Lifecycle Coordinator` (and the implied `core-orchestration` module).
*   **Blast Radius**: Almost every functional module depends on this layer:
    *   `macOS OSD HUD Overlay Renderer`
    *   `Menu Bar Agent Bootstrap`
    *   `PowerMate BLE GATT Transport`
    *   `macOS Audio Volume Controller`
    *   `PowerMate Gesture & Transport Facade`
    *   `PowerMate Custom Mode Action Engine`
    *   `macOS DisplayServices Brightness Controller`
    *   `MenuBar Status Icon Generator`
    *   `OSC UDP Message Sender`
    *   `PowerMate Profile Settings View`
    *   `Griffin PowerMate HID Transport Bridge`
    *   `PowerMate SPM Manifest & Framework Linker`

**Risk**: Any change to the event routing mechanism, state management, or initialization sequence in the Lifecycle Coordinator requires regression testing across the entire suite of hardware transports, UI renderers, and system controllers.

## Boundary Violations

Several modules exhibit dependencies that violate standard separation of concerns, specifically regarding Build Infrastructure and Documentation.

1.  **Runtime vs. Build Pipeline Coupling**:
    *   **Violation**: Runtime logic modules are importing `build-and-distribution`.
    *   **Evidence**:
        *   `PowerMate BLE GATT Transport` → `build-and-distribution`
        *   `macOS Audio Volume Controller` → `build-and-distribution`
        *   `DDC/CI I2C Display Command Bridge` → `build-and-distribution`
        *   `OSC UDP Message Sender` → `build-and-distribution`
        *   `Griffin PowerMate HID Transport Bridge` → `build-and-distribution`
    *   **Implication**: This suggests that version numbers, feature flags, or signing certificates are being accessed directly by hardware drivers. This makes unit testing difficult and couples the binary to the build script.

2.  **Application Shell Leakage**:
    *   **Violation**: A low-level display controller depends on the high-level application shell.
    *   **Evidence**: `macOS DisplayServices Brightness Controller` → `application-shell`.
    *   **Implication**: The brightness controller should be agnostic of the application's windowing or lifecycle shell. This creates a circular dependency risk if the shell also needs to control brightness.

3.  **Documentation as Code Dependency**:
    *   **Observation**: Modules like `PowerMateReborn Architecture Guide` and `PowerMateReborn User Documentation & Onboarding` are listed as modules with "no dependencies." While acceptable for static docs, if these are imported as code resources by other modules, it indicates a conflation of documentation and executable logic.

## Recommendations

### 1. Decouple Build Configuration from Runtime
Refactor the `build-and-distribution` dependency out of hardware and control modules.
*   **Action**: Create a dedicated `AppConfiguration` or `FeatureFlags` module that is generated at build time but exposed as a pure Swift struct/enum.
*   **Refactoring Target**:
    *   Update `Sources/Transport/PowerMateBLEGATTTransport.swift` to remove `build-and-distribution`.
    *   Update `Sources/Control/macOSAudioVolumeController.swift` to remove `build-and-distribution`.
    *   Inject configuration via the `PowerMateReborn Lifecycle Coordinator` during initialization instead of direct import.

### 2. Introduce a Domain Layer for Display Control
Resolve the inversion between the Display Controller and the Application Shell.
*   **Action**: Define a `DisplayControlProtocol` in a shared domain module. The `macOS DisplayServices Brightness Controller` should implement this protocol without knowing about `application-shell`.
*   **Refactoring Target**:
    *   Extract interface to `Sources/Domain/DisplayControlProtocol.swift`.
    *   Update `Sources/Control/macOSDisplayServicesBrightnessController.swift` to depend only on `Domain` and `CoreOrchestration`, removing `application-shell`.

### 3. Consolidate Fallback Strategies
The project currently has "Research & Fallback Strategy" stubs separate from the actual controllers.
*   **Action**: Merge the logic from `macOS Volume Control Research & Fallback Strategy` and `Display Brightness Control Research & Fallback Strategy` into their respective controller implementations or a shared `StrategyPattern` module.
*   **Refactoring Target**:
    *   Integrate `Sources/Research/macOSVolumeControlFallbackStrategy.swift` logic into `Sources/Control/macOSAudioVolumeController.swift`.
    *   Integrate `Sources/Research/DisplayBrightnessControlFallbackStrategy.swift` logic into `Sources/Control/macOSDisplayServicesBrightnessController.swift`.
    *   Delete the standalone research stubs once integrated to reduce maintenance overhead.

### 4. Stabilize the Core Orchestration Interface
Given the high blast radius of `PowerMateReborn Lifecycle Coordinator`:
*   **Action**: Define strict protocols for input ingestion and action dispatching. Ensure that transport layers (HID/BLE) only depend on an `InputSink` protocol rather than the concrete Coordinator class.
*   **Refactoring Target**:
    *   Create `Sources/Domain/InputSinkProtocol.swift`.
    *   Update `Sources/Transport/GriffinPowerMateHIDTransportBridge.swift` and `Sources/Transport/PowerMateBLEGATTTransport.swift` to depend on `InputSinkProtocol` instead of the concrete coordinator.