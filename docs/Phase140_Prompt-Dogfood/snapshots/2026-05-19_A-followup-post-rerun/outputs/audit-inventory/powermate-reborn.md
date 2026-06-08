## Component Table
| File | Role | Module | Summary | Lines | In-Degree |

Group by module. Include every file that has an augmentation summary.
Sort within each module by in-degree (most-imported first).

So the table should have rows grouped by module. In Markdown, grouping by module usually means having the module name as a header or grouping rows together. But the user wants a single table with those columns, and "Group by module". In Markdown tables, you can't really have row groups like HTML tbody. But you can either:
- Use a separate table per module, or
- Have a "Module" column and sort by module then by in-degree, or
- Insert header rows or separator rows.

The instruction says "Group by module." and the table format includes a "Module" column. So I think the best approach is to have one big table, sorted by Module (some logical order) and then by In-Degree descending within each module. But since the Module column is present, the grouping is visual. However, to make it clearer, I could use subheadings for each module with a small table, but the user specified a single table format: `| File | Role | Module | Summary | Lines | In-Degree |`. Actually, they said "Generate a Markdown document with: ## Component Table | File | Role | Module | Summary | Lines | In-Degree |". This suggests a single table. But "Group by module" with a single table means sorting by module and maybe adding bold separators? Markdown tables don't support row spans or grouping headers well. A common pattern is to have the Module column and sort by it. But the user explicitly says "Group by module." I can interpret this as: the rows should be ordered such that all rows of the same module are contiguous. I'll sort modules in some logical order (maybe by category or alphabetically) and then within each module by in-degree descending.

Alternatively, I could have multiple tables, one per module, each with the same columns but without the Module column? But the user specified the header with Module column. So I'll include the Module column in every row, and group by having contiguous rows. I'll also add a bold module header row? No, that breaks the table. I'll just sort by module name (alphabetical) then by in-degree descending. But wait, the user might want the module name to act as a section header. Let me re-read: "Group by module. Include every file that has an augmentation summary. Sort within each module by in-degree (most-imported first)." This could mean:
- Use module as the primary sort key.
- Use in-degree descending as the secondary sort key.

But to make grouping visually obvious, I could use a Markdown table where I insert a header row for each group? No, Markdown doesn't support that. I think the standard way in Markdown is to either have separate tables per group or just sort. Since the user gave a specific table header including "Module", I'll produce one table sorted by Module (alphabetically) and then by In-Degree descending. But to make it even clearer, I could add a horizontal rule or text between groups? The user said "Output ONLY the Markdown report" and "emit each section exactly once". Maybe I can have subsections per module, each with its own table. But the user said "Generate a Markdown document with: ## Component Table | File | Role | Module | Summary | Lines | In-Degree |". This implies one section with one table. However, "Group by module" is tricky in a single Markdown table.

Another interpretation: The user wants the table rows grouped by module, meaning the Module column values are grouped. I'll just ensure the rows are sorted by module. I'll order modules alphabetically. Within each module, sort by in-degree descending.

Wait, maybe I should order modules by their "importance" or category? The prompt doesn't specify module ordering. I'll use alphabetical order of module names for consistency.

Let me list all files with their mapped module, role (from file node category), summary, lines, in-degree:

1. Sources/AppDelegate.swift
   - Role: core
   - Module: Menu Bar Application Controller
   - Summary: Main application controller managing the PowerMate's operational modes, settings persistence, and ov... (truncated in prompt, but I should use what's given: "Main application controller managing the PowerMate's operational modes, settings persistence, and ov")
   - Lines: ~0
   - In-Degree: 4

2. docs/appcast.xml
   - Role: documentation
   - Module: Sparkle Appcast Feed
   - Summary: Sparkle framework appcast feed that provides update metadata, version history, and download links fo...
   - Lines: ~0
   - In-Degree: 4

3. Sources/BrightnessController.swift
   - Role: core
   - Module: Multi-Strategy Display Brightness Controller
   - Summary: Hardware abstraction layer for managing display brightness across built-in and external monitors usi...
   - Lines: ~0
   - In-Degree: 3

4. Sources/PowerMateManager.swift
   - Role: core
   - Module: PowerMate Hardware & Audio Volume Controller
   - Summary: Orchestrates hardware transports and implements gesture detection logic to convert raw button/rotati...
   - Lines: ~0
   - In-Degree: 3

5. Sources/CustomModeEngine.swift
   - Role: core
   - Module: PowerMate Custom Mode Action Engine
   - Summary: Logic engine for the PowerMate's custom mode, handling profile management and mapping knob inputs to...
   - Lines: ~0
   - In-Degree: 2

6. Sources/MIDIController.swift
   - Role: core
   - Module: CoreMIDI Virtual Source Controller
   - Summary: Virtual MIDI source manager that translates hardware knob and button inputs into MIDI Control Change...
   - Lines: ~0
   - In-Degree: 2

7. Sources/OSDOverlay.swift
   - Role: ui
   - Module: macOS OSD HUD Overlay
   - Summary: UI component that renders a native-style macOS On-Screen Display HUD with SF Symbols and level bars...
   - Lines: ~0
   - In-Degree: 2

8. Sources/PowerMateBLETransport.swift
   - Role: core
   - Module: PowerMate BLE Transport
   - Summary: Bluetooth Low Energy hardware interface for the Griffin PowerMate, translating BLE notifications int...
   - Lines: ~0
   - In-Degree: 2

9. Sources/PowerMateUSBTransport.swift
   - Role: core
   - Module: PowerMate USB HID Transport
   - Summary: USB HID hardware interface for the Griffin PowerMate, using IOKit to monitor device reports for rota...
   - Lines: ~0
   - In-Degree: 2

10. Sources/VolumeController.swift
    - Role: utility
    - Module: PowerMate Hardware & Audio Volume Controller
    - Summary: Provides a unified interface for controlling macOS system volume via CoreAudio, AppleScript, or soft...
    - Lines: ~0
    - In-Degree: 2

11. Package.swift
    - Role: config
    - Module: PowerMate Driver Package Manifest
    - Summary: Swift Package Manager manifest defining the project structure, dependencies like Sparkle, and system...
    - Lines: ~0
    - In-Degree: 1

12. Sources/CustomModeSettingsView.swift
    - Role: ui
    - Module: PowerMate Custom Mode Configuration UI
    - Summary: SwiftUI-based configuration interface for managing and editing custom PowerMate profiles and their a...
    - Lines: ~0
    - In-Degree: 1

13. Sources/DDCController.swift
    - Role: core
    - Module: Apple Silicon DDC Monitor Controller
    - Summary: Hardware interface for external monitors that sends DDC/CI commands via I2C to control brightness, v...
    - Lines: ~0
    - In-Degree: 1

14. Sources/MenuBarIcon.swift
    - Role: ui
    - Module: Menu Bar Vector Icon Renderer
    - Summary: Graphics utility that programmatically draws Lucide-style vector icons for the macOS menu bar using...
    - Lines: ~0
    - In-Degree: 1

15. Sources/OSCController.swift
    - Role: core
    - Module: OSC Network Message Sender
    - Summary: Network utility for sending Open Sound Control (OSC) messages over UDP to remote hosts for external...
    - Lines: ~0
    - In-Degree: 1

16. Sources/main.swift
    - Role: core
    - Module: macOS Cocoa Bootstrap & Signal Handler
    - Summary: The application's entry point, responsible for lifecycle management, signal handling for clean exit,...
    - Lines: ~0
    - In-Degree: 1

17. docs/research/RESEARCH_AUDIO.md
    - Role: documentation
    - Module: Project Research (or Research & Feasibility) — I'll call it "Research Documentation" to be safe. Actually, looking at the module dependencies, "PowerMateReborn Project Documentation" depends on "audio-research" and "brightness-research". These are likely the module names. So maybe the module for RESEARCH_AUDIO.md is "Audio Research" and for RESEARCH_BRIGHTNESS.md is "Brightness Research"? But the user wants to group by module. If I treat them as separate modules, that's fine. But there are 21 modules listed. The dependencies mention "audio-research" and "brightness-research" as dependency tags, not necessarily module names. However, the module list doesn't have entries for them. I'll create a single module "Research & Architecture" or "Feasibility Research". Let's use "Project Research" as the module name for both.
    - Summary: A comprehensive research guide and strategy matrix for implementing system-level volume control acro...
    - Lines: ~639
    - In-Degree: 1

18. docs/research/RESEARCH_BRIGHTNESS.md
    - Role: documentation
    - Module: Project Research
    - Summary: A comprehensive research guide outlining strategies for controlling macOS display brightness across...
    - Lines: ~755
    - In-Degree: 1

19. scripts/SPARKLE_SETUP.md
    - Role: documentation
    - Module: Sparkle Auto-Update Release Pipeline
    - Summary: Provides a step-by-step guide for configuring Sparkle 2 auto-updates, including key generation, GitH...
    - Lines: ~77
    - In-Degree: 1

20. scripts/appcast-template.xml
    - Role: script
    - Module: Sparkle Appcast Template
    - Summary: A reference template for the Sparkle RSS feed used to standardize the structure of new release entri...
    - Lines: ~0
    - In-Degree: 1

21. README.md
    - Role: documentation
    - Module: PowerMateReborn Project Documentation
    - Summary: A native Swift menu bar application designed to restore functionality to Griffin PowerMate USB and B...
    - Lines: ~112
    - In-Degree: 0

22. docs/README.md
    - Role: documentation
    - Module: PowerMateReborn Documentation Index
    - Summary: This document provides an overview of the PowerMateReborn project structure, detailing source files...
    - Lines: ~63
    - In-Degree: 0

23. scripts/CODE_SIGNING.md
    - Role: documentation
    - Module: macOS Code Signing & Release Orchestrator
    - Summary: Provides a step-by-step guide for code signing, notarizing, and releasing the PowerMateReborn macOS...
    - Lines: ~153
    - In-Degree: 0

24. scripts/build-dmg.sh
    - Role: script
    - Module: macOS DMG Builder & Code Signer
    - Summary: Automation script that compiles the application, signs the bundle with Developer ID, packages it int...
    - Lines: ~0
    - In-Degree: 0

Now, sorting modules alphabetically:
- Apple Silicon DDC Monitor Controller
- CoreMIDI Virtual Source Controller
- macOS Cocoa Bootstrap & Signal Handler
- macOS Code Signing & Release Orchestrator
- macOS DMG Builder & Code Signer
- macOS OSD HUD Overlay
- Menu Bar Application Controller
- Menu Bar Vector Icon Renderer
- Multi-Strategy Display Brightness Controller
- OSC Network Message Sender
- PowerMate BLE Transport
- PowerMate Custom Mode Action Engine
- PowerMate Custom Mode Configuration UI
- PowerMate Driver Package Manifest
- PowerMate Hardware & Audio Volume Controller
- PowerMateReborn Documentation Index
- PowerMateReborn Project Documentation
- PowerMate USB HID Transport
- Project Research
- Sparkle Appcast Feed
- Sparkle Appcast Template
- Sparkle Auto-Update Release Pipeline

Wait, that's 22 modules (including Project Research). Let me count: 21 original + 1 new = 22. Actually, I should check if "Project Research" is acceptable. Maybe I should instead map the research files to the "PowerMateReborn Project Documentation" module since that module depends on them. But that would put 3 files in that module: README.md (in-degree 0), RESEARCH_AUDIO.md (in-degree 1), RESEARCH_BRIGHTNESS.md (in-degree 1). Sorted by in-degree: research files first (1), then README (0). That might be more coherent and avoids inventing a module. The module description says "Dependencies: audio-research, brightness-research". This implies the research docs are inputs to the project documentation module. But are they part of it? The module is described as "Documents the native Swift menu bar application...". The research files are separate guides. However, grouping them under "PowerMateReborn Project Documentation" might be the most sensible way to avoid inventing modules. But the file docs/README.md is "PowerMateReborn Documentation Index" module. README.md is "PowerMateReborn Project Documentation". So there are already two README-related modules. Adding two more files to "PowerMateReborn Project Documentation" makes it a group of 3. That seems okay.

Alternatively, I could group them under a module named "Research" because they are in `docs/research/`. The user didn't explicitly define a module for them, but they are files in the codebase. The instruction "Group by module" might just mean "group by the module I assigned you". Since I have to assign them somewhere, I'll create a module called "Research & Feasibility" for the two research docs. This is honest about their unassigned status.

But wait, the file node says `docs/research/RESEARCH_AUDIO.md | documentation | unassigned`. The third field is literally "unassigned". Maybe the module is "unassigned"? That would be a valid group: all unassigned files together. There are exactly two unassigned files. Grouping them under "unassigned" is literally what the data says. But the user might not want an "unassigned" group. However, it's accurate to the provided file nodes. But the MODULES list doesn't have an "unassigned" module. The modules list seems to be the definitive list of modules. The file nodes have a "title" field, not necessarily "module". The prompt says "FILE NODES (24)" and the third column might be "component title". Then it says "MODULES (21)". So the modules are separate. The mapping is many-to-one. The research files are not mapped to any of the 21 modules. So I must either leave them out (but user says include every file) or map them to a module. Since they are documentation and support the project, I'll map them to a new module "Research & Architecture". But the user gave 21 modules. I think it's safer to put them in a group called "Research Documentation" or "Unassigned". Actually, looking at the module dependencies, "PowerMateReborn Project Documentation" depends on "audio-research" and "brightness-research". These are likely the two research files. So they are dependencies, not part of the module. But for the purpose of a component inventory, it's fine to list them as their own module or as part of the documentation suite.

I think the best approach is to use the module name "Research & Feasibility" for both. It's descriptive.

Now, let's finalize the order. I'll list modules alphabetically, but maybe I should group by category? The user didn't specify module ordering. Alphabetical is safe.

Module order:
1. Apple Silicon DDC Monitor Controller
2. CoreMIDI Virtual Source Controller
3. macOS Cocoa Bootstrap & Signal Handler
4. macOS Code Signing & Release Orchestrator
5. macOS DMG Builder & Code Signer
6. macOS OSD HUD Overlay
7. Menu Bar Application Controller
8. Menu Bar Vector Icon Renderer
9. Multi-Strategy Display Brightness Controller
10. OSC Network Message Sender
11. PowerMate BLE Transport
12. PowerMate Custom Mode Action Engine
13. PowerMate Custom Mode Configuration UI
14. PowerMate Driver Package Manifest
15. PowerMate Hardware & Audio Volume Controller
16. PowerMateReborn Documentation Index
17. PowerMateReborn Project Documentation
18. PowerMate USB HID Transport
19. Research & Feasibility
20. Sparkle Appcast Feed
21. Sparkle Appcast Template
22. Sparkle Auto-Update Release Pipeline

Wait, I need to check if "Sparkle Auto-Update Release Pipeline" should come before "Sparkle Appcast Feed" alphabetically? Yes: "Sparkle Auto..." vs "Sparkle App...". "Auto" comes before "App". Actually, alphabetically:
- Sparkle Appcast Feed
- Sparkle Appcast Template
- Sparkle Auto-Update Release Pipeline

Wait, "Appcast" vs "Auto". 'p' vs 'u'. "Appcast" comes before "Auto". So:
- Sparkle Appcast Feed
- Sparkle Appcast Template
- Sparkle Auto-Update Release Pipeline

Yes.

Now, within each module, sort by in-degree descending.

Let's list them properly:

**Apple Silicon DDC Monitor Controller**
- Sources/DDCController.swift | core | Apple Silicon DDC Monitor Controller | Hardware interface for external monitors that sends DDC/CI commands via I2C to control brightness, v... | ~0 | 1

**CoreMIDI Virtual Source Controller**
- Sources/MIDIController.swift | core | CoreMIDI Virtual Source Controller | Virtual MIDI source manager that translates hardware knob and button inputs into MIDI Control Change... | ~0 | 2

**macOS Cocoa Bootstrap & Signal Handler**
- Sources/main.swift | core | macOS Cocoa Bootstrap & Signal Handler | The application's entry point, responsible for lifecycle management, signal handling for clean exit,... | ~0 | 1

**macOS Code Signing & Release Orchestrator**
- scripts/CODE_SIGNING.md | documentation | macOS Code Signing & Release Orchestrator | Provides a step-by-step guide for code signing, notarizing, and releasing the PowerMateReborn macOS... | ~153 | 0

**macOS DMG Builder & Code Signer**
- scripts/build-dmg.sh | script | macOS DMG Builder & Code Signer | Automation script that compiles the application, signs the bundle with Developer ID, packages it int... | ~0 | 0

**macOS OSD HUD Overlay**
- Sources/OSDOverlay.swift | ui | macOS OSD HUD Overlay | UI component that renders a native-style macOS On-Screen Display HUD with SF Symbols and level bars... | ~0 | 2

**Menu Bar Application Controller**
- Sources/AppDelegate.swift | core | Menu Bar Application Controller | Main application controller managing the PowerMate's operational modes, settings persistence, and ov... | ~0 | 4

**Menu Bar Vector Icon Renderer**
- Sources/MenuBarIcon.swift | ui | Menu Bar Vector Icon Renderer | Graphics utility that programmatically draws Lucide-style vector icons for the macOS menu bar using... | ~0 | 1

**Multi-Strategy Display Brightness Controller**
- Sources/BrightnessController.swift | core | Multi-Strategy Display Brightness Controller | Hardware abstraction layer for managing display brightness across built-in and external monitors usi... | ~0 | 3

**OSC Network Message Sender**
- Sources/OSCController.swift | core | OSC Network Message Sender | Network utility for sending Open Sound Control (OSC) messages over UDP to remote hosts for external... | ~0 | 1

**PowerMate BLE Transport**
- Sources/PowerMateBLETransport.swift | core | PowerMate BLE Transport | Bluetooth Low Energy hardware interface for the Griffin PowerMate, translating BLE notifications int... | ~0 | 2

**PowerMate Custom Mode Action Engine**
- Sources/CustomModeEngine.swift | core | PowerMate Custom Mode Action Engine | Logic engine for the PowerMate's custom mode, handling profile management and mapping knob inputs to... | ~0 | 2

**PowerMate Custom Mode Configuration UI**
- Sources/CustomModeSettingsView.swift | ui | PowerMate Custom Mode Configuration UI | SwiftUI-based configuration interface for managing and editing custom PowerMate profiles and their a... | ~0 | 1

**PowerMate Driver Package Manifest**
- Package.swift | config | PowerMate Driver Package Manifest | Swift Package Manager manifest defining the project structure, dependencies like Sparkle, and system... | ~0 | 1

**PowerMate Hardware & Audio Volume Controller**
- Sources/PowerMateManager.swift | core | PowerMate Hardware & Audio Volume Controller | Orchestrates hardware transports and implements gesture detection logic to convert raw button/rotati... | ~0 | 3
- Sources/VolumeController.swift | utility | PowerMate Hardware & Audio Volume Controller | Provides a unified interface for controlling macOS system volume via CoreAudio, AppleScript, or soft... | ~0 | 2

**PowerMateReborn Documentation Index**
- docs/README.md | documentation | PowerMateReborn Documentation Index | This document provides an overview of the PowerMateReborn project structure, detailing source files... | ~63 | 0

**PowerMateReborn Project Documentation**
- README.md | documentation | PowerMateReborn Project Documentation | A native Swift menu bar application designed to restore functionality to Griffin PowerMate USB and B... | ~112 | 0

**PowerMate USB HID Transport**
- Sources/PowerMateUSBTransport.swift | core | PowerMate USB HID Transport | USB HID hardware interface for the Griffin PowerMate, using IOKit to monitor device reports for rota... | ~0 | 2

**Research & Feasibility** (or whatever I name it)
- docs/research/RESEARCH_AUDIO.md | documentation | Research & Feasibility | A comprehensive research guide and strategy matrix for implementing system-level volume control acro... | ~639 | 1
- docs/research/RESEARCH_BRIGHTNESS.md | documentation | Research & Feasibility | A comprehensive research guide outlining strategies for controlling macOS display brightness across... | ~755 | 1

Wait, if I put them in "Research & Feasibility", the Module column will say that. But is there a better name? Maybe "System Research"? Or just "Research Documentation"? I'll use "Research Documentation" to be clear.

Actually, looking back at the prompt, the MODULES section lists modules with names. The research files are not in any module. But the user says "Group by module." If I invent a module name, I'm fabricating. But if I use "unassigned", I'm being literal to the file node's third column. The file node says `unassigned` for the title. But the user says "Group by module." The modules are the 21 listed. Since the research files are not in any module, perhaps they should be listed under an "Unassigned" module or omitted? But the user says "Include every file that has an augmentation summary." So they must be included. I'll use "Unassigned" as the module name for them. It's literally what the file node says. But the file node's third column might be the title, not module. However, since the user didn't provide a module mapping for them, "Unassigned" is a reasonable group label.

Alternatively, I could map RESEARCH_AUDIO.md to "Audio Research" and RESEARCH_BRIGHTNESS.md to "Brightness Research" as implied by the dependencies of the Project Documentation module. But those aren't official module names. I'll stick with "Unassigned" or "Research". Let's use "Research" — it's neutral and descriptive.

Actually, I just realized: the MODULES list has 21 entries. The file nodes have 24 files. The mapping I did earlier covers 22 files (21 modules, one module has 2 files). The two research files are the leftovers. The prompt might intentionally have unmapped files to see how I handle them. Using "Unassigned" is the most accurate to the source data (since the file node's title field says "unassigned"). But the file node's title field is not the module. However, there's no other field. I'll use "Unassigned" as the module group. It signals that these files are not part of a defined architectural module.

But wait, the user might want the module names from the MODULES list exactly. If I use "Unassigned", it's not from the list. But it's a valid grouping label. I'll use "Unassigned" and put the two research files there.

Let me reconsider the sorting of modules. Maybe I should sort by category first?