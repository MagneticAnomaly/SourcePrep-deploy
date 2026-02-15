# Organic/Personal Post Draft for r/cursor

## Title Options
1. **My Cursor `@codebase` kept failing on my monorepo, so I built a local fix**
2. **Finally fixed the "hallucinated imports" problem in Cursor (built a local MCP tool)**
3. **I got tired of pasting files manually. Here is the local indexer I built for Cursor.**

## Body Structure

### The Pain
I've been using Cursor daily for months. It's amazing. But on my larger project (a messy monorepo), the `@codebase` indexing just wasn't cutting it. It would constantly miss the file I *actually* needed, or I'd have to manually `@mention` 10 different files to get it to understand a change.

### The Fix
I decided to solve it myself. I built **CoDRAG**, a local app that sits in the background and builds a **real dependency graph** of the code.

It runs as an **MCP Server**, which Cursor now supports natively.

### How it changes the workflow
Now, instead of hoping Cursor guesses the right file, I just ask my custom tool. It traces the imports and injects *only* the relevant code (interfaces, type defs) into the chat.

It's been a game changer for me—less "Apply" failures, less hallucinations.

### It's free for local use
I built it for myself and my team, but I packaged it up as a proper app. If you're hitting context limits, give it a shot.

**Link:** [Link]

## Tone
"Fellow Cursor user sharing a life hack." Frustration turned into a solution.
