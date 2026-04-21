# Post Draft for r/kubernetes

## Title Options
1. **Tooling: A local indexer to help LLMs navigate massive K8s repos (without uploading them)**
2. **Indexing thousands of manifests locally for AI context**

## Body Structure

### Hook
Navigating a massive repo of Helm charts, Kustomize overlays, and operator logic is a nightmare for LLMs. They hallucinate resource names constantly.

### The Solution
I built **Prep**, a local context engine. While it's built for code, it handles repo structure well. It builds a graph of your files locally.

### Use Case
Connect it to your editor via MCP, and when you ask "Where is the ingress for the `payments` service defined?", it traces the file paths to find the definition, rather than guessing.

### Links
*   **Repo:** [Link]

## Tone
Brief, tool-focused.

## Timing
Weekday.
