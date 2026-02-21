LLMLingua-2 remains the primary current version of Microsoft’s task-agnostic compression model. While a "LLMLingua-3" has not been officially released, there is a newer, specialized adaptation called **LLMLingua-2 Dynamic**. 

Below is an overview of the latest developments for natural language and specialized models for code.

### 1. The Latest in the LLMLingua Family
*   **LLMLingua-2 Dynamic:** A 2024/2025 adaptation that introduces **query-awareness**. Unlike the standard version, it dynamically adjusts the compression ratio based on the specific question asked, allowing it to preserve more information for complex queries while being more aggressive on simple ones.
*   **LongLLMLingua:** Specifically designed for RAG (Retrieval-Augmented Generation) scenarios. It focuses on reordering context to put the most important information at the beginning or end of the prompt to avoid the "lost-in-the-middle" phenomenon.
*   **MInference:** A related 2024 tool from the same Microsoft team. It isn't a text compressor per se, but it uses a sparse-attention mechanism to speed up processing of prompts up to 1 million tokens by 10x without losing accuracy.

### 2. Similar Natural Language Models
If you are looking for alternatives to LLMLingua-2 for general text, these are the top competitors:
*   **500xCompressor:** An advanced method that can compress massive natural language contexts into as few as a single "special token" (soft-prompting), achieving ratios up to 480x.
*   **CPC (Context-aware Prompt Compression):** A sentence-level compressor that uses a context-aware encoder to rank the relevance of each sentence to a specific question.
*   **Nano-Capsulator:** Instead of deleting tokens, it summarizes the original prompt into a concise "capsule" that is more fluent and readable for the LLM.
*   **Selective Context:** An earlier but still popular model that uses self-information (entropy) to identify and remove redundant tokens.

---

### 3. Models for Compressing Code
Standard NLP compressors often "break" code by removing vital brackets or syntax. For code, you should look at models that understand **Abstract Syntax Trees (AST)**:

| Model/Tool | Method | Best Use Case |
| :--- | :--- | :--- |
| **LongCodeZip** (2025) | A two-stage framework that ranks code at the **function level** first, then prunes tokens within those functions. | Large repositories where you need to keep structural logic intact. |
| **Stingy Context (TREEFRAG)** | Uses a hierarchical tree structure to represent the codebase, achieving a massive **18:1 compression ratio**. | Auto-coding tasks where architectural fidelity is more important than raw text. |
| **Repomix** | A popular tool that uses **Tree-sitter** to extract function signatures and class structures while stripping away implementation details. | Packaging entire projects into a single "AI-friendly" file. |
| **Aider's Repo-Map** | Creates a "map" of your codebase (signatures, definitions) to give the LLM a high-level view without including the whole file content. | Integrated into the Aider CLI for real-time coding assistance. |

**Recommendation for Code:**
If you want to save tokens while keeping code functional, **LongCodeZip** or **Repomix** are your best options. They don't just "delete words"; they understand that a `class` definition is more important than a `print` statement and ensure that the code remains valid syntax for the LLM to process.
