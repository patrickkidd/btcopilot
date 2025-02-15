# BT Copilot

AI Chatbot service for Bowen theory - the human family as a bioliogical unit
with clinical applications.

## Provides:

- A Large Language Model (LLM) RAG engine trained on a defined corpus of
  academic literature.
- A REST service to access the engine.

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

# Development Journal

- 2025-02-10 Trained gpt2 model on Bowen's book, with garbage from titles, page numbers,
  etc. Took four hours on i9 macbook pro and responses had mediocre sentance
  structure with too much focus on a few passages.
```
  It is essentially impossible to know the percentage who get married and who do not get divorced. At thi
s level of differentiation, differentiation does not begin to take place until there is a certain percentage of people who are sufficien tly involved with their families of origin to begin differentiation without emotional participation in the family emotional system.
do well on tests of differentiation have a reasonable chance of getting a social or professional degree,
if they keep the effort on their families of origin. Results are less with this approach if the family effort is with a spouse in the 30 to 40 range.
People in the 50 to 75 range get married within a few generations. There are those who get married within a few generations and continue for life and who terminate marriage within the next five to ten years. Those with very low levels of differentiation have an infinite n umber of satisfying marriages with intact families and those with a high level of fusion who terminate marriage within several generatio
A typical marriage is one in which the basic level of differentiation is transmitted in marriage, but it is not manifested in children.
There are marriages in which the basic level is transmitted in children who use various combinations of marriage mechanisms and 385 other outside relationships to raise the basic level of differentiation. There are marriages in which the basic level is transmitted in marriage and where it continues in subsequent marriages, but the transmission is less intense and symptoms are less intense.
Marriages in which the basic level is transmitted in marriage are called stable marriages and in which there are no symptoms,
the sympto
ms are more episodic and it is not as serious and long-term as with less severe emotional illness and less severe emotional illness and less long-term transmission of the problem to a spouse with good levels of differentiation. There are marriages in which the basic level is transmitted in marriage where the basic level is sufficiently submerged in the marriage to be seen only with one or two children to
be meaningful symptoms but symptoms are less intense and transmission is less serious and
is much less intense than with severe illness
and less long-term transmission of the problem to one or two children.
People in the 65 to 70 range get married within a few generations. There are others who do well with a few children and maintain self in the 30 to 40 range until the problems subside and thereafter it is seen as the "fusion" phenomenon with a child who gets "programmed" t o the family projection process with the parents. The children grow up
  ```
- 2025-02-11 Colleague suggested langchain with RAG. Used RAG with cloud-based `groq` llm
  and chroma vector db produced better answers but sometimes couldn't find any
  relevant data.
- 2025-02-13 Watching many youtube videos on RAG including better pdf
  processing, different llm's, etc. Found better pdf copy of Bowens book w/o
  page numbers, Pre-processed Bowen's book into chapters without titles.
  epigraphs. Include book name and chapter title from file names in langchain
  doc metadata. Per-chapter pdf ingestion took ~54 seconds.
  - Returned in ~54 seconds for "What are the four anxiety binding mechanisms?"
```
Response:  The provided context does not explicitly mention the term "anxiety binding mechanisms" or list any specific four mechanisms. However, it suggests several patterns and dynamics that help maintain emotional equilibrium in a family system, which can be perceived as "anxiety binding." These include:

1. Triangle patterns - interpersonal relationships involving three people where one person's actions affect the other two, creating a cycle of tension and reaction.
2. Projection process - the tendency for individuals to transfer their own unacceptable impulses, feelings or traits onto others, allowing them to avoid acknowledging these aspects within themselves.
3. Patterns of transfer anxiety - ways in which anxiety is passed between individuals, with variations such as a mother forcing anxiety or psychosis onto a resisting patient.
4. The level of integration and differentiation of self - refers to the organism's ability to adapt and cope with anxiety, emphasizing the importance of maintaining emotional equilibrium within oneself.

These patterns and dynamics help bind anxiety in a family system by addressing and managing stress and tension within relationships, promoting emotional stability.

Sources: ['22 - Toward the Differentiation of Self in Ones Family of Origin.pdf', '18 - Society Crisis and Systems Theory.pdf', '18 - Society Crisis and Systems Theory.pdf', '16 - Theory in the Practice of Psychotherapy.pdf', '1 - Treatment of Family Groups with a Schizophrenic Member.pdf']
```
  - Returned in ~54 seconds for: "What is differentiation of self?"
  ```
  Response:  Differentiation of self, as described in the given context, refers to a concept that deals with an individual working on their own self, controlling their emotions, becoming more responsible, and permitting others to be themselves. It's analogous to the process of differentiation in biology, where cells separate from each other for specialized functions. In this theoretical system, higher levels of differentiation equate to emotional maturity. The level of differentiation may depend on factors like the level of differentiation of one's parents and the nature of the relationship between the child and their parents.

Sources: ['9 - The Use of Family Theory in Clinical Practice.pdf', '12 - Alcoholism and the Family.pdf', '17 - An Interview with Murray Bowen.pdf', '16 - Theory in the Practice of Psychotherapy.pdf', '16 - Theory in the Practice of Psychotherapy.pdf']
  ```
- 2025-02-15: First copilot chat in app UI! The answers are slow, but they work!
  ![BT Copilot Logo](./doc/first_copilot_chat.jpg)
  - LLM: `deepseek-r1:14b`
  - Embeddings: `sentence-transformers/all-MiniLM-L6-v2`