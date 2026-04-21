# macOS Distribution

## Purpose
Document macOS distribution options and constraints for a Tauri app that bundles a Python sidecar.

## Two distribution tracks

### Track A: Direct distribution (Developer ID)
Use this for:
- MVP distribution outside the App Store
- enterprise pilots

Key requirements:
- Code signing requires an Apple Developer account.
  - https://v2.tauri.app/distribute/sign/macos/
- Notarization is required when using a Developer ID Application certificate.
  - https://v2.tauri.app/distribute/sign/macos/

Operational notes:
- Notarization requires Apple authentication configured for Tauri.
- Tauri docs describe two approaches:
  - App Store Connect API credentials
  - Apple ID + app-specific password

Reference:
- https://v2.tauri.app/distribute/sign/macos/

### Track B: Mac App Store distribution
Use this for:
- a public App Store release

High-level requirements:
- Apple Developer Program enrollment.
- Register the app in App Store Connect.
- Code signing.

Reference:
- https://v2.tauri.app/distribute/app-store/

#### App Sandbox requirement
Tauri notes that App Sandbox capability is required to distribute in the App Store.

Reference:
- https://v2.tauri.app/distribute/app-store/

#### Provisioning profile requirement
Tauri documents the need for a Mac App Store Connect provisioning profile and configuring it to be embedded in the app bundle.

Reference:
- https://v2.tauri.app/distribute/app-store/

#### Encryption export compliance
Tauri’s App Store doc calls out adding an Info.plist setting for encryption export regulations.

Reference:
- https://v2.tauri.app/distribute/app-store/

## Python sidecar constraints on macOS

### Bundling the sidecar
Tauri supports bundling external binaries via `externalBin`.

Reference:
- https://v2.tauri.app/develop/sidecar/

Important notes:
- Separate binaries per target triple are required (suffix `-$TARGET_TRIPLE`).
  - https://v2.tauri.app/develop/sidecar/

### Running the sidecar
Tauri recommends using the shell plugin and `shell().sidecar()`.

Reference:
- https://v2.tauri.app/develop/sidecar/

## App Store risks and open questions
- App Sandbox context can restrict filesystem access.
  - Prep’s core workflow requires reading codebases; ensure the “add repo → build → search” workflow works in sandbox context.
  - Tauri explicitly notes: “Make sure your app works when running in an App Sandbox context.”
    - https://v2.tauri.app/distribute/app-store/
- Validate that bundling and executing a Python sidecar is acceptable under App Store review constraints.

## Suggested MVP path
- Start with direct distribution (Developer ID + notarization) to validate the product loop and reduce App Store friction.
- Treat Mac App Store distribution as a parallel research/validation track, because sandbox + sidecar constraints can become schedule blockers.
