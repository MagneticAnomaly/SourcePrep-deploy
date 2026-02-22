# Model Recommendations Research TODO

Research and finalize model recommendations for both **BYOK (cloud)** and **Ollama (local)** workflows.

## BYOK (Cloud API) Models

We need cost-effective recommendations for each model slot when using Bring-Your-Own-Key cloud providers.

### Research Questions

- [x] **Anthropic**: Sonnet 4.5 ($3/$15, 64K output) is best value. Haiku 3.5 ($0.80/$4, 8K output) for budget. Opus 4.6 is overkill.
- [x] **OpenAI**: GPT-4.1-nano ($0.10/$0.40) is ultra-cheap budget pick. GPT-4.1-mini ($0.40/$1.60) is best value.
- [x] **Google**: Gemini 2.5 Flash ($0.15/$0.60) is cheapest viable. Gemini 2.5 Pro ($1.25/$10) for quality.
- [x] **Batch size mapping**: Claude 4.5+ → Large. GPT-4.1/GPT-5 → Standard. Gemini Flash/Haiku 3.5/DeepSeek → Compact.
- [x] **Per-slot recommendations**: Yes — split model setup saves money. Cheaper model for Fast, better for Thinking.
- [x] **Cost estimates**: ~$0.36/1K files (Gemini Flash) to ~$9.45/1K files (Claude Sonnet). See MODEL_RECOMMENDATIONS_RESEARCH.md.

### Updated Recommendations (in Cloud Processing card)

- **Budget:** `gpt-4.1-nano` — $0.10/$0.40, Standard batch
- **Best value:** `gpt-4.1-mini` — $0.40/$1.60, Standard batch
- **Cheapest:** `gemini-2.5-flash` — $0.15/$0.60, Compact batch
- **Premium:** `claude-sonnet-4.5` — $3/$15, Large batch (64K output)

✅ **Validated and updated** — see MODEL_RECOMMENDATIONS_RESEARCH.md for full analysis.

---

## Ollama (Local) Models

Update the Model Recommendations info box at the bottom of AI Models settings.

### Research Questions

- [x] **Fast/Small slot**: `qwen3:4b` (2.5GB) is now best — rivals Qwen2.5-72B at this size. Ministral-3 and qwen2.5 are outclassed.
- [x] **Thinking/Large slot**: `qwen3:8b` (5.2GB) primary. `qwen3:14b` (9.3GB) or `qwen3:30b` MoE (19GB) for more VRAM.
- [x] **Code slot**: `qwen3-coder:30b` MoE (19GB, 3.3B active) is best. Alt: `qwen2.5-coder:7b` for lower VRAM.
- [x] **Embedding**: nomic-embed-text-v1.5 via ONNX — confirmed, no change needed (Phase 33).
- [x] **Performance**: Qwen3 family is a generational leap. MoE architecture means 30B models run with 3B active params.

### Updated Recommendations (in info box)

- Embedding: nomic-embed-text-v1.5 (Built-in ONNX — no Ollama needed)
- Fast: qwen3:4b (2.5GB). Alt: qwen3:1.7b for low VRAM
- Thinking: qwen3:8b (5.2GB). Alt: qwen3:14b (9.3GB), qwen3:30b MoE (19GB)
- Code: qwen3-coder:30b MoE (19GB, 3.3B active). Alt: qwen2.5-coder:7b

✅ **Updated in AIModelsSettings.tsx**

---

## Design Decisions (Finalized)

- **Context window**: Irrelevant for all slots. Fast sees ~1K tokens, Thinking sees ~4K max. Even 40K models have 10× headroom.
- **GPU speed tiers**: 3 qualitative tiers (High-end / Fast / Standard) with examples. Affects messaging, not model selection.
- **Single-model edge case**: VRAM ≤ 4GB → recommend 1 model for all slots (qwen3:4b or smaller). Suggest Hybrid.
- **Cloud**: 1 or 2 models max per provider. No 3-model setup. Code always uses Fast.
- **Hybrid**: 1 local (Fast) + 1 cloud (Thinking). Code falls back to local Fast. Always 2 total.
- **Selection parameters that matter**: VRAM footprint, JSON reliability, reasoning quality. NOT context window.

---

## Action Items

1. ~~Research pricing and output limits for all providers~~ ✅ Done
2. ~~Update Cloud Processing card recommendations~~ ✅ Done
3. ~~Update Ollama info box~~ ✅ Done
4. ~~Update batch_profiles.py model registry~~ ✅ Done
5. ~~Update Storybook stories~~ ✅ Done
6. ~~Finalize design decisions for ModelAdvisor~~ ✅ Done
7. [ ] Build ModelAdvisor component
   - [ ] GPU database (`gpu-database.ts`) — VRAM + speed tier per GPU
   - [ ] Model database (`model-database.ts`) — VRAM + quality tier per model
   - [ ] Recommendation engine — pure function `(mode, vram?, provider?) → ModelPlan`
   - [ ] ModelAdvisor.tsx — Local / Hybrid / Cloud selector + results
   - [ ] Wire into AIModelsSettings.tsx — replace info box
   - [ ] "Apply" action — populate slot configs from recommendation
8. [ ] Add docs page with full model comparison table

**Full research:** `docs/Phase35_BYOK/MODEL_RECOMMENDATIONS_RESEARCH.md`
