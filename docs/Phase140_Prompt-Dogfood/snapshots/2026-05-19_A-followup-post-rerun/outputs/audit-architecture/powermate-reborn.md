## Architecture Overview

PowerMateReborn is a native Swift macOS menu-bar utility that interfaces with Griffin PowerMate USB and Bluetooth hardware. The codebase is organized into four conceptual tiers:

1. **Hardware & Transport** — `PowerMate USB HID Transport`, `PowerMate BLE Transport`, and `Apple Silicon DDC Monitor Controller` handle low-level I/O (IOKit HID, CoreBluetooth, DDC/CI).
2. **Domain & Action** — `PowerMate Hardware & Audio Volume Controller` mediates raw input into semantic gestures; `PowerMate Custom Mode Action Engine`, `OSC Network Message Sender`, and `CoreMIDI Virtual Source Controller` dispatch external actions.
3. **Application & Presentation** — `Menu Bar Application Controller` orchestrates the headless menu-bar lifecycle; `PowerMate Custom Mode Configuration UI`, `macOS OSD HUD Overlay`, `Menu Bar Vector Icon Renderer`, and `Multi-Strategy Display Brightness Controller` provide user-facing feedback and controls.
4. **Build & Release** — `PowerMate Driver Package Manifest`, `Sparkle Appcast Feed`, `Sparkle Appcast Template`, `Sparkle Auto-Update Release Pipeline`, `macOS DMG Builder & Code Signer`, and `macOS Code Signing & Release Orchestrator` manage packaging, signing, and auto-update distribution.

The architecture is heavily centralized around `application-lifecycle-controller` (materialized chiefly in `Menu Bar Application Controller` and `