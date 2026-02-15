# Post Draft for r/OpenAI

## Title Options
1. **Stop pasting 50 files into ChatGPT: I built a local context engine**
2. **A better way to feed codebase context to o1/4o (Structural Graph vs Text Dump)**

## Body Structure

### Hook
We've all done the "Copy entire folder -> Paste into ChatGPT" dance. It works... until it doesn't.

### The Problem
Models like o1 are smart, but they hallucinate APIs if they don't see the exact definition.

### The Solution: CoDRAG
I built a local tool that creates a compressed, structural map of your code.
You can use it to generate a "Context Prompt" that contains *only* the functions and types relevant to your bug, drastically reducing the noise you feed to the model.

### Links
*   **Repo:** [Link]

## Tone
Problem/Solution focused.

## Timing
Weekday.
