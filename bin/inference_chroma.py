def query_rag(query_text: str):
    from langchain.prompts import ChatPromptTemplate
    from btcopilot import vector_db, LLM_MODEL

    # from langchain_community.llms.ollama import Ollama
    from langchain_ollama import OllamaLLM

    PROMPT_TEMPLATE = """
Ansert the following question based only on the following context: {context}

---
Answer the question based on the above context: {question}
"""
    NUM_RESULTS = 5

    results = vector_db.similarity_search_with_score(query_text, k=NUM_RESULTS)
    print(f"Using {len(results)} matching results.")

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)

    model = OllamaLLM(model=LLM_MODEL)
    response_text = model.invoke(prompt)

    sources = [doc.metadata.get("chapter_id", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\n\nSources: {sources}"
    print(formatted_response)
    # return response_text


def main():
    import argparse

    # Create CLI.
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_text = args.query_text
    query_rag(query_text)


main()
