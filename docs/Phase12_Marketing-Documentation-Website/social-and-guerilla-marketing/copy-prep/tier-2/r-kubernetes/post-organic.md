# Organic/Personal Post Draft for r/kubernetes

## Title Options
1. **Helping LLMs understand my Helm chart spaghetti (Local Graph Tool)**
2. **Indexing thousands of K8s manifests without uploading them**

## Body Structure

### The Mesh
My K8s repo is a mess of overlays, charts, and values files.
Asking an LLM "where is this port defined?" usually fails because the value is passed through 3 different files.

### The Fix
I built **CoDRAG** to trace these dependencies.
It builds a graph. It finds the links.
It runs locally.

**Link:** [Link]

## Tone
"K8s is hard, let's make it easier."
