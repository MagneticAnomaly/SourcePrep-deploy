# Organic/Personal Post Draft for r/devops

## Title Options
1. **I built a local-only code search tool for air-gapped environments**
2. **No cloud, no telemetry: A self-hosted indexer for your team's code**

## Body Structure

### The Security Problem
I work in an environment where "uploading code to SaaS" is a firing offense.
But we still wanted AI coding features.

### The Tool
I built **Prep**. It runs entirely on `localhost`.
It builds a structural index of the repo without any external API calls.
We use it to feed context to our local LLMs (Ollama) securely.

Check it out if you have similar compliance constraints.

**Link:** [Link]

## Tone
Security-conscious professional.
