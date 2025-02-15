
# Development Journal

## 2025-02-10 - Fine-tuned GPT2 model

Trained gpt2 model on Bowen's book, with garbage from titles, page numbers,
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

## 2025-02-11 - Langchain and RAG

Colleague suggested langchain with RAG. Used RAG with cloud-based `groq` llm
  and chroma vector db produced better answers but sometimes couldn't find any
  relevant data.

## 2025-02-13 - Pre-processed Bowen's book into chapter pdfs

Watching many youtube videos on RAG including better pdf
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
## 2025-02-15 - First Copilot UI!

The answers are slow, but they work! Still need to show expandable list of sources with passages.
  ![BT Copilot Logo](./first_copilot_chat.jpg)
  - LLM: `mistral`
  - Embeddings: `sentence-transformers/all-MiniLM-L6-v2`

## 2025-02-15 - Automatically testing model's accuracy

I defined a set of [quiz questions with expected correct answers](../btcopilot/tests/data/quizzes.py). The quiz will be improved as time goes on.

Example Passing answer:

```
**** QUESTION:What are the two positions in a triangle called?

**** EXPECTED ANSWER:Inside and outside

**** RECEIVED ANSWER: Answer:  In the given context, the two positions in a triangle are not explicitly named. However, they can be inferred as the close twosome and the outsider. The close twosome is the pair that forms the base of the triangle, while the outsider is the third person who is not part of the close relationship but interacts with both members of the twosome.
Sources: ['21 - On the Differentiation of Self.pdf', '16 - Theory in the Practice of Psychotherapy.pdf', '21 - On the Differentiation of Self.pdf', '21 - On the Differentiation of Self.pdf', '10 - Family Therapy and Family Group Therapy.pdf']
Vector DB Time: 1.8134565340005793
LLM Time: 36.359419119005906
Total Time: 38.17371924100007

INFO     test_model:test_model.py:56 Copilot vector db time: 1.8134565340005793
INFO     test_model:test_model.py:57 Copilot llm time: 36.359419119005906
INFO     test_model:test_model.py:58 Copilot total time: 38.17371924100007
```
