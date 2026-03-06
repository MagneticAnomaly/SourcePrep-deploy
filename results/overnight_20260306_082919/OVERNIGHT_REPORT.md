# Overnight Qwen Benchmark Report: TEST Repo
*Tested on real Next.js marketing site (`TEST`): 97 nodes (45 symbols, 44 files), 127 edges*

## Time & Speed (Hardware: Apple Silicon via Ollama)

| Config | Total Time | Augment (Pass 1) | Epistemic (Pass 2) | Cluster (Pass 3) |
|---|---|---|---|---|
| **9b-nothink** | 20.3 min | 336s (~3.8s/item) | 674s (~15.3s/file) | 207s |
| **35b-a3b-nothink** | **18.7 min** | 291s (~3.2s/item) | **621s** (~14.1s/file) | 209s |
| **35b-a3b-think** | **18.4 min** | **242s** (~2.7s/item) | **623s** (~14.2s/file) | 242s |
| **27b-nothink** | 54.3 min | 927s (~10.4s/item) | 1787s (~40.6s/file) | 541s |

**Key finding:** The MoE model (`35b-a3b`) is surprisingly the **fastest** across the board. It beat the 9b model by ~1-2s per file in the epistemic pass. The 27b dense model is, as expected, 3-4× slower. "Think" mode on the MoE did not slow it down significantly, suggesting the `think` parameter in Ollama for this specific model architecture doesn't incur the massive token overhead we saw with the 27b.

---

## Quality Metrics

| Config | Epistemic Confidence | Unique Domain Tags | Module Count | Module Quality |
|---|---|---|---|---|
| **9b-nothink** | **0.941** | 58 | 22 | Poor (e.g., "Ui (Src) #4", "Ui (.) #2") |
| **35b-a3b-nothink** | 0.925 | **61** | 21 | OK (mix of "Ui (Docs)" and "DebateHaus Marketing UI") |
| **35b-a3b-think** | 0.925 | 57 | 25 | Better (e.g., "TypeScript Build Configuration", "Ui Media Queries & Animation Control") |
| **27b-nothink** | 0.921 | 55 | 21 | Poor (e.g., "Ui/Ux", "Ui (Src) #2") |

### Observations on Quality

1. **Augment Summaries:** All models produced highly accurate, 1-2 sentence summaries. For example, for `src/app/page.tsx`, the 35b-a3b-think generated: *"Main application entry point for the homepage UI with signup form and hero section."*
2. **Epistemic Summaries (Deep Analysis):**
   - **9b:** Focuses heavily on the technical orchestration ("orchestrating the user interface by integrating the EnhancedHero component for scroll-driven animations").
   - **35b-a3b (Think):** More narrative and role-focused ("orchestrating the user interface by integrating the EnhancedHero component for visual engagement and the BetaSignupForm modal").
3. **Domain Tags:** The MoE no-think model extracted the most unique conceptual tags (61), capturing nuanced domains like `branding`, `scroll-interaction`, and `governance`.
4. **Module Generation (Pass 3):** This is where all models struggled with the current prompts. They all produced generic names like "Ui (Src) #4". However, **`35b-a3b-think` performed best** here, generating the most descriptive names like "Ui Media Queries & Animation Control" and "TypeScript Build Configuration" instead of just numbered generic buckets.

## Conclusion & Recommendations

1. **Bug Fixed:** The `stream=True` fix in `LLMClient` completely eliminated the timeout hangs. All 4 pipeline runs completed with 0 failures out of 176 epistemic file enrichments.
2. **Fast Slot Winner:** The **`qwen3.5:35b-a3b`** model. It is faster than the 9b model (~14s vs ~15s per file) and produces richer domain tags. 
3. **Deep Slot Winner:** If speed is paramount, the `35b-a3b` with thinking enabled is a great compromise, as it generated the best module names without the 3x time penalty of the 27b. However, the 27b dense model still remains the baseline for deep code reasoning when time permits.
