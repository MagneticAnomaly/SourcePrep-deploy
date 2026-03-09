# Phase 45: Multi-GPU Concurrency Research

This document outlines the research and findings regarding the implementation of multi-GPU and multi-node concurrency in the CoDRAG pipeline. The design specifications based on this research are found in `DESIGN.md`.

## 1. The Core Problem

CoDRAG pipelines heavily utilize large language models (LLMs) for tasks like augmentation, epistemic enrichment, clustering, and audit synthesis. Currently, the system assumes a single, monolithic compute environment.

The problem manifests in several ways:
1. **Resource Exhaustion (OOM):** If three projects are processing simultaneously, they might all request the "Deep Model" (e.g., a 35B parameter model) at the same time. This immediately overloads the VRAM of a single GPU, causing Out-Of-Memory errors and crashing the LLM server.
2. **Timeout Failures:** Even if the LLM server queues the requests internally (like Ollama sometimes attempts), the requests take so long to process sequentially that the HTTP clients in the CoDRAG orchestrator time out waiting for a response.
3. **Underutilization of Distributed Hardware:** Users with a MacBook for development and a dedicated Linux workstation with an RTX 4090 cannot efficiently utilize both machines. The pipeline cannot route "fast" tasks to the Linux box while keeping "deep" tasks on the MacBook with its massive unified memory.

## 2. Hardware Constraints & Context Sizing (Phase 46 Overlap)

Phase 46 research explicitly proved that context window size and "think mode" have a massive impact on token generation speed and VRAM requirements.

*   **Mac Unified Memory:** Apple Silicon can allocate large contiguous blocks of memory, allowing 128GB Macs to run 70B+ models or multiple instances of 32B models. However, it lacks a true "swap" mechanism for the GPU. Exceeding the `recommendedMaxWorkingSetSize` (typically ~75% of total RAM) causes catastrophic performance degradation as the OS aggressively pages memory.
*   **NVIDIA Discrete GPUs:** NVIDIA GPUs have strict VRAM limits (e.g., 24GB on a 4090). However, Ollama and LM Studio can offload layers to system RAM if a model exceeds VRAM. This prevents crashing but significantly slows down inference speed (especially for MoE models where expert routing across the PCIe bus becomes a bottleneck).

**Conclusion:** The pipeline scheduler must act as a strict gatekeeper. It cannot rely on the LLM server to handle queuing because the LLM server does not understand the pipeline's timeout constraints or the specific hardware topology.

## 3. The `ComputeNode` Abstraction

The fundamental solution is to model compute resources explicitly. A `ComputeNode` represents a discrete hardware environment capable of running LLMs.

A `ComputeNode` requires:
*   **Capacity (`max_concurrent`):** The absolute maximum number of simultaneous LLM requests this specific hardware can handle without timing out or OOMing.
*   **Hardware Profile:** Knowing if the node is `apple_silicon`, `nvidia`, or `cloud` informs the user on how to tune the `max_concurrent` setting (e.g., an NVIDIA 4090 might handle 2x 8B models concurrently, while a cloud endpoint can handle 50+).

The existing "Saved Endpoints" (e.g., `http://192.168.1.100:11434`) are mapped *to* a `ComputeNode`. This decouples the network address from the hardware capacity.

## 4. Pipeline Scheduling vs. LLM Server Queuing

Why build a scheduler in CoDRAG when Ollama has an internal queue?

1. **Visibility:** CoDRAG needs to show the user "Project A is queued waiting for the Linux Box". Ollama's internal queue is a black box.
2. **Timeouts:** HTTP requests to Ollama will timeout if they sit in the internal queue too long. The CoDRAG scheduler holds the task *before* making the HTTP request, preventing network timeouts.
3. **Multi-Node Routing:** Ollama only knows about itself. It cannot route a task to a different machine. CoDRAG needs to coordinate across multiple Ollama instances.
4. **State Machine Integrity:** The CoDRAG pipeline is a formal state machine. Halting execution requires a formal `QUEUED` state rather than just blocking on a hanging HTTP call.

## 5. Summary of the Multi-Project Coordinator

The research concludes that a centralized `MultiProjectCoordinator` is required. It holds the state of all `ComputeNodes` (their `max_concurrent` vs. currently executing tasks). 

When a project orchestrator reaches an LLM stage, it *requests* a slot. If granted, it proceeds. If denied, the orchestrator transitions to a `QUEUED` state and yields execution. When a slot opens up, the coordinator wakes the orchestrator up via a `STAGE_DEQUEUED` event.

## 6. Real-World Benchmarking (LinuxBrain Overnight)

To validate the multi-repo scaling and hardware assumptions, we ran a comprehensive 10-hour benchmark on the **LinuxBrain** repository (a complex Vue/Electron/Python application with ~4,900 lines of code across 467 files, generating 4,751 symbols).

### 6.1 Data Exclusion Discoveries
A critical finding during the LinuxBrain benchmark was the necessity of rigorous directory exclusion. The initial trace attempt discovered **10,909 nodes**, estimating 17 hours for augmentation. 

Root cause analysis revealed two massive non-code directories:
- `halley_core/frontend/src-tauri/target/`: **20GB** of Rust build artifacts.
- `data/humanai/`: **24GB** of vector databases and JSONL datasets.

**Takeaway:** The CoDRAG indexer must aggressively exclude `target/`, `build/`, `dist/`, and large `data/` directories by default. Parsing binary artifacts or multi-gigabyte vector databases completely stalls the LLM pipeline and wastes compute cycles.

### 6.2 Augmentation Performance
The augmentation phase (Phase 1) processed 4,751 symbols using the `qwen3.5:35b-a3b` Q4 model.
- **Average Speed:** ~6.8 seconds per item.
- **Total Time:** ~9 hours for the full augmentation pass.

This perfectly validates the single-node concurrency limits. A single Apple Silicon machine (M3 Max/Ultra) running a 35B model at Q4 precision achieves a stable 6.8s/item throughput over a 9-hour sustained run without VRAM swapping or degradation.

### 6.3 Implications for Multi-GPU
The 9-hour augmentation time for a medium-sized repo (467 files) highlights exactly why Phase 45 (Multi-GPU Concurrency) is mandatory for enterprise users. 

If a user has 3 such repositories, sequentially augmenting them on a single machine would take **27 hours**. 
With the `MultiProjectCoordinator` design:
- A user could assign Repo 1's augmentation to a local Mac Studio (Node A).
- Assign Repo 2's augmentation to a local Linux Workstation with an RTX 4090 (Node B).
- Assign Repo 3's augmentation to a RunPod cloud instance (Node C).

By decoupling the pipeline state machine from a single hardware constraint, the total wall-clock time drops back down to 9 hours, fully utilizing the user's available compute fleet.

## 4. Pipeline Scheduling vs. LLM Server Queuing

Why build a scheduler in CoDRAG when Ollama has an internal queue?

1. **Visibility:** CoDRAG needs to show the user "Project A is queued waiting for the Linux Box". Ollama's internal queue is a black box.
2. **Timeouts:** HTTP requests to Ollama will timeout if they sit in the internal queue too long. The CoDRAG scheduler holds the task *before* making the HTTP request, preventing network timeouts.
3. **Multi-Node Routing:** Ollama only knows about itself. It cannot route a task to a different machine. CoDRAG needs to coordinate across multiple Ollama instances.
4. **State Machine Integrity:** The CoDRAG pipeline is a formal state machine. Halting execution requires a formal `QUEUED` state rather than just blocking on a hanging HTTP call.

## 5. Summary of the Multi-Project Coordinator

The research concludes that a centralized `MultiProjectCoordinator` is required. It holds the state of all `ComputeNodes` (their `max_concurrent` vs. currently executing tasks). 

When a project orchestrator reaches an LLM stage, it *requests* a slot. If granted, it proceeds. If denied, the orchestrator transitions to a `QUEUED` state and yields execution. When a slot opens up, the coordinator wakes the orchestrator up via a `STAGE_DEQUEUED` event.


## 7. Next Steps for Abstract Hardware Profiles
As part of Phase 45, we must simplify the UX for configuring `max_concurrent`. Users shouldn't need to know if their "Apple Silicon" allows 1 or 4 instances; the UI should abstract this away.

**New UX Design:**
Instead of a "Hardware Profile" dropdown, we use a single **LLM Concurrency** setting with clear hardware guidance.

```
LLM Concurrency: [ 1 | 2 | 3 | 4 | 6 | 8 ]

Guidance Text:
- 1: Single GPU, 8-16GB VRAM (Mac M1/M2, RTX 3060)
- 2: 16-32GB VRAM (Mac M3/M4, RTX 3070/4060)
- 4: 32-48GB VRAM (Mac Pro/Ultra, RTX 4090)
- 6+: 64GB+ VRAM or multiple GPUs
```
This removes the false equivalence between hardware type and concurrency capability, making it purely about memory capacity. The `ComputeNode` data model will still store `max_concurrent`, but the frontend will present it in this unified way.
