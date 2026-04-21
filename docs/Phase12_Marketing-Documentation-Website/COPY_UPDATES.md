# Prep Marketing Copy Updates (Phase 12)

This document tracks planned copy updates across the marketing website to reflect our evolving stance on cloud vs local LLMs, Ollama integration, and general clarity improvements.

## 1. Cloud vs Local AI Positioning
**Context:** Our current copy heavily emphasizes "local-first" and often implies that users *should* use local models or Ollama, or that cloud is an afterthought. However, recent research (Phase 46) and practical use cases show that while the *embedding and graph index* must be local, using cloud LLMs (BYOK - Bring Your Own Key) for *graph enrichment and reasoning* is often significantly better (e.g., Claude 3.5 Sonnet, Gemini 1.5 Pro) due to better reasoning and large context windows. We need to clearly separate the "local index" from the "flexible AI reasoning engine."

### `FeatureBlocks.tsx`
**Old:** 
> "Ask 'where is the auth middleware?' and get ranked results in under 100 ms. Built-in ONNX embeddings (nomic-embed-text) work out of the box — or connect Ollama or a cloud API like OpenAI if you prefer an alternative model."
**New:**
> "Ask 'where is the auth middleware?' and get ranked results in under 100 ms. Fast, privacy-first ONNX embeddings run locally out of the box — or connect your preferred cloud AI provider (BYOK) if you want alternative embedding models."

**Old:**
> "Your code index stays on localhost. Use the built-in local models for zero network traffic, or connect to a cloud provider (BYOK) for enhanced trace understanding — you're in control."
**New:**
> "Your code index stays strictly on localhost. The entire structural trace graph and embedding index are built offline. When it's time for AI reasoning, you're in control: use local models for zero network traffic, or securely connect a frontier cloud provider (BYOK) for maximum intelligence."

### `CompetitorMatrix.tsx`
**Old (LLM Augmentation):**
> "Local / BYOK LLM Epistemic Pipeline"
**New:**
> "Flexible AI Pipeline (Cloud BYOK or Local)"

### `TechStackMatrix.tsx`
**Old:**
> "The Rust-powered daemon that runs entirely on your machine. Indexes codebases of any size — 500 files or 500,000 — with built-in semantic embeddings. No Ollama, no cloud, no GPU required."
**New:**
> "The Rust-powered daemon runs entirely on your machine. It indexes codebases of any size — 500 files or 500,000 — with built-in local semantic embeddings. The core index requires no GPU, no cloud, and no external AI sidecars. You optionally plug in cloud LLMs just for reasoning."

## 2. Clarifying Local Requirements & Ollama
**Context:** We want to make it explicitly clear that Prep does *not* require Ollama to function. It ships with its own ONNX embedding model for search.

### `app/faq/page.tsx` (FAQ: Is my code uploaded to the cloud?)
**Old:**
> "What makes this different from tools that claim local-first: Prep ships its own embedding model (ONNX, runs on CPU) and its own Rust parser. You don't need Ollama, you don't need Docker, you don't need an internet connection for core functionality. The entire stack runs offline, cold."
**New:**
> "What makes this different from tools that claim local-first: Prep ships its own local embedding model (ONNX, runs on CPU) and Rust parser. You don't need an internet connection, Docker, or external tools like Ollama for the core indexing and search functionality to work out of the box."

## 3. New FAQs to Add

### FAQ: Should I use a local model or a cloud API for reasoning?
**Proposed Draft:**
> **Q: Should I use a local model or a cloud API for reasoning?**
> **A:** For the absolute best results, we recommend bringing your own API key (BYOK) for frontier cloud models like Anthropic Claude 3.5 Sonnet, OpenAI o3-mini, or Google Gemini 1.5 Pro. These models have massive context windows and superior reasoning capabilities for complex codebase analysis. 
> 
> However, if strict data privacy is required (e.g., enterprise compliance, air-gapped environments), you can easily connect local models via Ollama. Prep is designed to support both seamlessly. The code *index* itself always remains 100% local on your machine.

### FAQ: Does Prep require a powerful GPU?
**Proposed Draft:**
> **Q: Does Prep require a powerful GPU?**
> **A:** No. The core Prep indexing engine, structural graph generation, and ONNX embeddings all run highly efficiently on standard CPUs. You only need a powerful GPU if you choose to run large local reasoning models (like Qwen or Llama 3) via Ollama instead of using cloud APIs.

## 5. Additional Marketing Pages (Home, Compare, Security)

### `app/compare/prep-vs-greptile/page.tsx`
**Old:**
> "Cloud indexers often charge steep per-seat monthly fees and mark up token costs. Prep offers a one-time perpetual license option and fully supports Bring Your Own Key (BYOK). If you want to use Anthropic Claude 3.5 Sonnet or OpenAI o3-mini for reasoning, you pay exactly what the API costs—not a penny more. Or, connect local models via Ollama for entirely free inference."
**New:**
> "Cloud indexers often charge steep per-seat monthly fees and mark up token costs. Prep offers a one-time perpetual license option and fully supports Bring Your Own Key (BYOK). The core index runs locally for free. For reasoning, use Anthropic Claude 3.5 Sonnet or OpenAI o3-mini and pay exactly what the API costs—not a penny more. Or, connect local models via Ollama for entirely free inference."

### `app/page.tsx` (Homepage SEO/Intro text)
**Old:**
> "Prep is a local-first codebase indexing and context assembly engine designed for AI-assisted development... By integrating directly via the Model Context Protocol (MCP)... Prep provides highly compressed, structurally-aware context to AI models, ensuring they have perfect understanding of multi-repo environments without exposing code to cloud APIs."
**New:**
> "Prep is a local codebase indexing and context assembly engine designed for AI-assisted development... By integrating directly via the Model Context Protocol (MCP)... Prep provides highly compressed, structurally-aware context to AI models. Your code index stays perfectly secure on your machine, while you freely connect your choice of cloud APIs or local models for reasoning."

### `app/security/page.tsx` (Security architecture details)


## 6. Pricing / Feature Grids
### `app/pricing/page.tsx`
**Old:**
> "Built-in embeddings — add Ollama or BYOK cloud for enrichment"
**New:**
> "Built-in local embeddings — connect frontier cloud APIs or local models for advanced reasoning"
