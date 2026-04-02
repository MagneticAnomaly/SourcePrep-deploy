# Model Pruning and Centralization Plan

## Objective
To eliminate documentation drift and reduce the maintenance burden when new LLM generations (like Qwen4 or Claude 4.5) are released. We will achieve this by **pruning** specific model references from peripheral marketing/docs and creating designated **Conceptual Centers**.

## 1. Prune the Surface Area

The goal is to replace specific, hardcoded model strings with generic, future-proof terminology across the vast majority of the website. 

### Marketing Site Refactoring
*   **Status:** Needs Update
*   **Target:** `websites/apps/marketing/src/app/`
*   **Action:** 
    *   Change specific BYOK strings (e.g., `Claude 3.5 Sonnet`, `o3-mini`, `Gemini 1.5 Pro`) to generic descriptors: "frontier cloud models from Anthropic and OpenAI" or "leading reasoning APIs."
    >> this is a little too much, We can saely talk about Claude Sonnet and Claude Opus, and Gemini Pro, just avoid numbers -- we can identify specific places for the specific reccommendations but in the marketing site we want to discuss models, but not THAT specific. This requare far less maintience
    *   Change specific local strings (e.g., `Qwen2.5-72B`) to "leading small local models via Ollama."
    >>> same here we cn use Qwen and Kimi, etc. these later on will be reccommended so we can technically expose "kimi-k2.5:cloud" in marketing (like on animated demos etc) but keep track of these this is what w can make into a variable
*   **Specific Files to Target:** 
    *   `compare/codrag-vs-greptile/page.tsx`
    *   `faq/page.tsx`

### Peripheral Documentation Refactoring
*   **Status:** Needs Update
*   **Target:** `websites/apps/docs/src/app/guides/` (excluding the Centers)
*   **Action:** 
    *   Change terminal CLI examples that hardcode models to use generalized placeholders.
    *   Example: `--model-name gpt-4.1-mini` becomes `--model-name <your_cloud_model>`.
    *   Example: `RUN ollama pull qwen3:8b` becomes `RUN ollama pull <your_local_model>`.
*   **Specific Files to Target:** 
    *   `dynamic-model-loading/page.tsx`
    *   `byok-batching/page.tsx`
    *   `enterprise-deploy/page.tsx`
    *   `team-sync/page.tsx`


---
>>> Thie will likely need an overhaul, we have a great start and we need to continue to maintain it yes but a reimagining is eminant. this whould be a shold new phase.

## 2. Designate Conceptual Centers

These are the **only** two pages in the entire website ecosystem permitted to contain specific LLM model version strings, VRAM estimations, or GPU recommendations.
>>> again I think we need a couple exceptions like the landing page needing to use "kimi-k2.5:cloud" . we at least need a componet to bea able to handle a couple of these "hardcoded" model names.

*   **Center 1: The Model Advisor (`model-advisor/page.tsx`)**
    *   *Purpose:* Real-time hardware calculation and tactical recommendation generation.
    *   *Permitted Strings:* Specific Ollama names (`qwen3:14b`), VRAM GB metrics, cloud names (`claude-sonnet-4.5`).
*   **Center 2: The Core Models Guide (`models/page.tsx`)**
    *   *Purpose:* The master reference list for the CoDRAG application.
    *   *Permitted Strings:* Detailed descriptions of the Qwen3 family, why it's chosen, MoE VRAM breakdown, and exact embedding model tags.

**Maintenance Protocol:** When an AI lab releases a new foundational model that benefits the CoDRAG architecture, you only need to update these two `.tsx` pages.

---

## 3. The Tracker (Anti-Drift Script)
<<< the seems kile overkill just updates it, provide guidence in the pages comments and make these updates>>>

To ensure this strategy holds over time and that marketing drift does not creep back in, we are introducing a verification script.

*   **Script Location:** `docs/Phase68_revise-marketing/audit_model_references.mjs` *(Move to `websites/apps/scripts/` upon execution).*
*   **Functionality:** 
    1. Scans all `.tsx`, `.ts`, and `.mdx` files in the `websites/apps` monorepo.
    2. Uses a dictionary of "Stale" labels (e.g., `gpt-4o`, `Qwen2:`, `claude-3.5-sonnet`).
    3. Fails (exit code 1) if these stale labels are found anywhere.
    4. Triggers soft warnings if "Tracked" labels (current active models) are found outside of the two Conceptual Center pages.

### Execution Plan for CI
When this plan is executed, add the execution of `node scripts/audit_model_references.mjs` to the GitHub Actions `build.yml` or Turborepo pipeline. This ensures a PR cannot be merged if bombastic model drift creeps into the marketing FAQ or peripheral tutorials.
