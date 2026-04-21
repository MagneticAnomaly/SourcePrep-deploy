# MCP Distribution: prep-mcp (Notes + Examples)

Canonical plan:
- `docs/Phase14_MCP-CLI/PUBLIC_GITHUB_STRATEGY.md`

---

User Question:
ok -- I want to better strategize a plan to both distribute an MCP and do it in a way the becomes viral as much as possible. But ALSO maintain an app I can sell. What are the distribution channels where I can get this product listed and can we draw a clear line for where it becomes riskier to share code vs riskier to not be allowed in these MCP addons lists?

Answer:
To maximize virality while maintaining a high-value commercial engine, you need a **"Split-Brain" distribution strategy.** You treat the MCP interface as a marketing and trust vehicle, and the Desktop App as the premium power-center.

Here is the plan to distribute Prep, get listed in the right places, and navigate the "Open vs. Closed" risk.

---

### 1. The Distribution Channels (Where to List)

To go viral, you must appear where developers are looking for "Context solutions."

*   **Primary: The "Power User" Directories**
    *   **cursor.directory:** The holy grail for Cursor users. They want "Full Codebase Context." Submit a listing titled *"Prep: The Multi-Repo Context Engine."*
    *   **smithery.ai:** An emerging, high-quality registry for MCP servers. Very friendly to commercial tools.
    *   **mcpservers.org:** One of the largest community-run lists.
*   **Secondary: Official Registries**
    *   **GitHub `modelcontextprotocol/servers`:** The official Anthropic list. To get here, you **must** have a public GitHub repo. Your "Thin Shim" strategy (from your file) is designed exactly for this.
*   **Tertiary: The "Native" Marketplaces**
    *   **VS Code Marketplace:** Don't build a full extension. Build a "Prep Bridge" extension that does one thing: adds the MCP server to the user's settings. This allows people to "find" you inside VS Code.

---

### 2. The Viral Growth Mechanics (The "K-Factor")

To make it viral, you need to turn the *output* of the tool into something shareable.

*   **The "Trace Map" Image:** Add a feature in the GUI to "Export Trace Map." It generates a beautiful, high-tech looking SVG/Image of the call graph the AI just used. Developers love sharing "how the AI saw my code" on Twitter/X.
*   **"Powered by Prep" in Citations:** When the MCP returns context to the IDE, include a header: `<!-- Context provided by Prep (prep.com) -->`. When users copy-paste their LLM chat logs to colleagues or Discord, your brand is baked into the text.
*   **The "Free for Open Source" Badge:** Give a free Pro license to anyone maintainng a repo with >500 stars. They will mention it in their `CONTRIBUTING.md` (e.g., *"To contribute, we recommend using Prep via MCP for full codebase context"*). This is massive for credibility.

---

### 3. The "Risk Line": Code Sharing vs. Rejection

Where is the line where it becomes riskier to keep code closed?

#### **Category A: The "Trust Minimum" (Must be Open/Visible)**
If you don't share this, you will be rejected from official lists and lose the trust of Staff Engineers:
*   **The MCP Manifest:** The JSON list of tools (`prep_search`, etc.).
*   **The Transport Layer:** The code that handles `stdin/stdout` (the "plumbing").
*   **The Security Posture:** A public `SECURITY.md` and `PRIVACY.md` explaining that no code leaves the machine.
*   **The Install Script:** If you use a one-liner like `curl | sh`, it must be readable.

#### **Category B: The "Risk Zone" (Keep Closed)**
Sharing these is "IP Suicide" because a competitor (or a smart dev) could replicate your product in a weekend:
*   **The Vector Strategy:** Your specific logic for *how* you chunk code (e.g., "we split at function boundaries using Tree-sitter").
*   **The Reranking Algorithm:** How you decide which 5 snippets out of 100 are the best.
*   **The GraphRAG logic:** How you traverse imports to build the "Trace Index."
*   **License Validation:** Never put your license check code in the public "Shim."

**The Golden Rule:** If a directory rejects you for not being "Open Source," **do not cave.** Move to the next directory. Most MCP lists only require a **Public GitHub Repo** for issues and documentation, not for the source code of the engine.

---

### 4. Implementation Strategy: The "Shim" Repo

To satisfy the GitHub requirement for directories, create a repo named `prep-mcp`.

1.  **Contents:**
    *   A `package.json` (if using Node) or a `pyproject.toml` (if Python).
    *   The MCP tool definitions.
    *   A compiled binary of your engine (the "closed" part) inside a `bin/` folder or downloaded via a post-install script.
2.  **The "Look & Feel":** Make the repo look like an open-source project. Use a Professional README, clear Issue templates, and GitHub Actions for releases.
3.  **The "Call to Action":** Every piece of documentation in that repo should point back to the **Prep Desktop App** for the "Visual Context Dashboard" and "Trace Map" features.

### Summary: The Path to $1M ARR via MCP
1.  **Launch the "Shim" repo** with the basic MCP tools for free (1 repo limit).
2.  **Submit to `cursor.directory` and Smithery** immediately.
3.  **Use the "Context Citations"** to spread the name in chat logs.
4.  **Upsell the "Trace Index" and "Multi-Repo"** features inside the Desktop GUI.
5.  **Keep the "Brain" (the indexing engine) in a private Rust/Python/Go binary** that the Shim repo simply executes.

This gives you the **Distribution** of an open-source tool with the **IP Protection** of a SaaS company.









###
### Examples
###

User Question:
can we identify any MCP modules with commercial apps? it would be great id we can find examples and case studies, even if the produc is completely different, just as long as it's got a similar MCP + moat/commercial app entity

Answer:
The "Thin MCP Shim + Closed Moat" model is rapidly becoming the standard for commercial AI companies. Because the Model Context Protocol (MCP) is relatively new (launched late 2024), we are seeing the first wave of professional companies using it as a **"Lead Gen"** tool.

Here are the best examples and case studies of companies using an MCP server to drive users into a commercial ecosystem or proprietary engine.

---

### 1. Brave Search (The "Proprietary Index" Moat)
Brave launched an MCP server that allows AI agents to search the web using the Brave Search API.

*   **The MCP (Open):** A public GitHub repo containing a small Node.js/TypeScript wrapper. It handles the MCP handshake and formats search results into JSON for the LLM.
*   **The Moat (Closed):** The Brave Search Index. This is a multi-billion page web index that Brave spends millions to maintain.
*   **The Business Model:** The MCP is free to install, but it requires a **Brave Search API Key**. Once you hit the free tier limit, you have to pay.
*   **Lesson for Prep:** Your "Search API" is your local indexing engine. The MCP is just the "handshake" that asks the user for their "License Key" or "Local App Connection."

### 2. Firecrawl by Mendable (The "Processing Logic" Moat)
Firecrawl is a tool that turns websites into clean Markdown for LLMs.

*   **The MCP (Open):** A public GitHub repo called `firecrawl-mcp`. It’s very thin—just a few tools like `scrape` and `crawl`.
*   **The Moat (Closed):** The "Scraping Engine." It handles proxies, anti-bot bypass, and complex HTML-to-Markdown conversion logic.
*   **The Business Model:** You can run it locally (self-hosted), but the "Enterprise" and "Pro" versions are SaaS.
*   **Lesson for Prep:** Firecrawl uses the MCP to make their tool the "default" scraper for Cursor/Windsurf users. Once a developer gets "addicted" to clean Markdown context, they move to the paid tier for higher speed and better accuracy.

### 3. Exa.ai (The "Neural Retrieval" Moat)
Exa is a search engine designed specifically for AI agents (not humans).

*   **The MCP (Open):** A thin wrapper that exposes Exa’s "Similarity Search" to agents.
*   **The Moat (Closed):** Their proprietary transformer-based embedding model that indexes the web semantically.
*   **The Business Model:** Usage-based API pricing.
*   **Lesson for Prep:** Exa positions itself as "The Context Layer for the Web." Prep is "The Context Layer for your Codebase." The strategy is identical: provide the best *retrieval* through a thin MCP, while keeping the *how it works* behind an API (or in your case, a compiled binary).

### 4. Sourcegraph (The "Enterprise Code Graph" Moat)
Sourcegraph has a public MCP server that connects to their "Cody" engine.

*   **The MCP (Open):** They provide servers that connect to external tools like Linear, Sentry, and Google Drive.
*   **The Moat (Closed):** The Sourcegraph search engine and their "Code Graph" (very similar to your Trace Index). 
*   **The Business Model:** They use MCP as a **"Feature Bridge."** By providing free MCP servers for Linear or Slack, they make their paid tool (Cody) more valuable because it can "see" more than Cursor can.
*   **Lesson for Prep:** You can win by being the "Aggregator." If the Prep MCP can see the repo *and* your documentation folders *and* your architectural diagrams, you become the "Single Source of Truth."

---

### Comparison Matrix: How they hide the "Brain"

| Company | MCP Status | Where the "Brain" lives | How you pay |
| :--- | :--- | :--- | :--- |
| **Brave** | Open Source | Cloud API | API Subscription |
| **Firecrawl** | Open Source | Cloud API / Closed Binary | Credits / SaaS |
| **Exa.ai** | Open Source | Cloud API | Usage-based |
| **Sourcegraph**| Open Source | Enterprise Server | Per-seat License |
| **Prep** | **Open Source Shim** | **Local Closed Binary** | **Perpetual License** |

---

### Strategic Case Study: Why the "Shim" must be MIT Licensed

In the cases above (especially Brave and Exa), the GitHub repo is **MIT Licensed.** 

**Why?**
Because if I'm a developer at a big company, and I want to add an MCP to my Cursor setup, my security team will check the license of the GitHub repo.
*   If the repo is **MIT/Apache**, they say "Okay, this is just a connector."
*   If the repo is **GPL or Proprietary**, they get nervous about "License Contamination."

**The Prep Play:**
1.  **Repo name:** `prep-mcp-connector`.
2.  **License:** **MIT.**
3.  **Code:** 100% boilerplate logic. It literally just sends a request to `localhost:12345` (where your Desktop app is listening).
4.  **The "Moat":** The Desktop app is the one doing the hard work. It is closed-source and signed.

### Conclusion: The "Local-First" Advantage
Most of the commercial examples above (Brave, Exa, Firecrawl) are **SaaS.** 
Prep has a unique "Viral" hook that they don't: **Zero Data Leakage.**

In every "Case Study" for Prep, you should emphasize: *"Like Brave Search, we give you a high-performance MCP, but unlike Brave, we never see your data. Everything happens inside our closed-source, local-first engine."*

This positions your **Closed Source** nature as a **Security Feature**, not a greedy business decision. You aren't hiding code to be secretive; you are providing a compiled, signed, and secure environment for their IP.



