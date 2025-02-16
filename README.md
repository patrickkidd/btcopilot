# BT Copilot

AI Chatbot service for Bowen theory - the human family as a bioliogical unit
with clinical applications.

[Development Journal](doc/JOURNAL.md).

## Provides:

Python API for a Large Language Model (LLM) RAG engine trained on a defined
corpus of clinical and scientific literature. Literature: [btcopilot/index.py](botcopilot/index.py)

## Sources

- Seminal literature Bowen theory
    - Terms: Differentiation of self, triangles, etc
- Collective Behavior and Intelligence
    - Center for Collective Behavior, Max Planck Institute of Animal Behavior (https://www.ab.mpg.de/couzin)
- More to come: Sapolski, All the psychologists, etc.

# Wiki

https://github.com/patrickkidd/btcopilot/wiki/Frankenstein-Phase-%E2%80%90-R&D

# Token Limits for Popular Models

- GPT-4 (8k and 32k token models):
  - Default GPT-4 has a context window of 8,192 tokens.
  - GPT-4-32k offers a larger 32,768 token window, but it's more expensive and slower.
- Mistral and similar open-source LLMs:
  - Typically have 4k–8k token limits (depending on the specific model and configuration).
- Tokens include all text: your prompt + the model's response. So, a 4k-token model leaves room for ~3k tokens for input and ~1k for output.

Practical Numbers:
- A single token is roughly 4 characters in English.
- For GPT-4 (8k): ~6,000 words total for the entire conversation (timeline + literature + user query + LLM response).

Here’s a rough idea of token usage:
- Timeline (10 years, summarized)	~500 tokens
- Academic context (5 chunks)	~2,000 tokens
- Prompt structure and query	~500 tokens
- Total	~3,000 tokens
This fits comfortably within an 8k-token model. For larger datasets, you'd need summarization, chunking, or a larger context model.

