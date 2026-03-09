Ollama’s cloud service (introduced in late 2025/early 2026) allows you to run massive models that wouldn't fit on your local GPU by offloading the computation to their servers. 

### 1. How to Use Cloud Models
You do not need a new application; you use the existing Ollama CLI or API, but you must authenticate first.

**Via CLI (The easiest way):**
1. **Sign in:** Run `ollama signin` in your terminal. This will open a browser window to link your local Ollama instance to your [ollama.com](https://ollama.com) account.
2. **Run the model:** Use the `:cloud` suffix to tell Ollama to use the remote host.
   ```bash
   ollama run kimi-k2.5:cloud
   ```
   *Note: When you run a cloud model, Ollama won't download the massive weights (e.g., 1TB for Kimi K2); it only downloads the small manifest file.*

**Via Direct API (No local Ollama needed):**
If you want to use the cloud models in a script without running the Ollama background service locally:
*   **Endpoint:** `https://ollama.com/api`
*   **API Key:** Log into your account on [ollama.com](https://ollama.com), go to **Settings > API Keys**, and generate a key.
*   **Usage:** Set the `OLLAMA_API_KEY` environment variable or use a Bearer token in your header:
    ```bash
    curl https://ollama.com/api/chat -H "Authorization: Bearer <your_key>" -d '{
      "model": "kimi-k2.5:cloud",
      "messages": [{"role": "user", "content": "Hello!"}]
    }'
    ```

---

### 2. Pricing and Plans
Ollama uses an **"Intensity-Based"** usage model rather than a strict token count. They do not sell "1 million tokens for $1"; instead, they sell "capacity levels."

| Plan | Price | Target Usage | Expectation |
| :--- | :--- | :--- | :--- |
| **Free** | $0 | Light experimentation | A few dozen messages per hour. Good for testing if a model works for your task. |
| **Pro** | $20/mo | Day-to-day work | Designed for developers using it for RAG, coding (e.g., via `cline` or `aider`), and long chats. |
| **Max** | $100/mo| Heavy/Production | 5x more capacity than Pro. Designed for autonomous agents and batch processing. |

### 3. Usage & Token Expectations
Because Ollama doesn't publish a "hard" token number, your experience will depend on **Fair Use** and **Concurrency**:

*   **Tokens per month:** While not officially capped, the **Pro ($20)** plan is generally optimized for roughly **10–20 heavy coding sessions per week**. If you use it 24/7 for automated batch processing, you will likely hit a "429 Too Many Requests" error or a temporary throttle (often reported as a 4-hour or weekly "usage percentage" in your dashboard).
*   **Hourly/Daily limits:** Limits are dynamic based on server load. During peak times, Free users may experience slower response times (latency) or lower message caps than Pro users.
*   **Concurrency:** On the **Free** tier, you can typically only run one cloud model at a time. The **Pro** tier allows you to run multiple cloud models simultaneously (useful for multi-agent workflows).
*   **Data Privacy:** Unlike most cloud providers, Ollama Cloud explicitly states they **do not retain or train** on your prompt/response data, which is why many users choose the $20 plan over ChatGPT/Claude.

### Important Note on "kimi-k2.5:cloud"
Models like **Kimi-K2.5** are Mixture-of-Experts (MoE) models with nearly 1 trillion parameters.