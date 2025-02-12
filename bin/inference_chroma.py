import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langsmith import tracing_context
import torch

# Directories
VECTOR_DB_DIR = "./data"

# Load the vector database and embedding model
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vector_db = Chroma(
    collection_name="academic_docs",
    persist_directory=VECTOR_DB_DIR,
    embedding_function=embeddings,
)


def run_one():
    from langchain import hub
    from langchain_core.documents import Document
    from langgraph.graph import START, StateGraph
    from typing_extensions import List, TypedDict
    from langchain.chat_models import init_chat_model

    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    llm = init_chat_model("llama3-8b-8192", model_provider="groq")

    # Define prompt for question-answering
    prompt = hub.pull("rlm/rag-prompt")

    # Define state for application
    class State(TypedDict):
        question: str
        context: List[Document]
        answer: str

    # Define application steps
    def retrieve(state: State):
        retrieved_docs = vector_db.similarity_search(state["question"])
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])
        messages = prompt.invoke(
            {"question": state["question"], "context": docs_content}
        )
        response = llm.invoke(messages)
        return {"answer": response.content}

    # Compile application and test
    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    graph = graph_builder.compile()

    response = graph.invoke({"question": "What mistake did Freud make?"})
    print(f'Context: {response["context"]}\n\n')
    print(f'Answer: {response["answer"]}')


def similarity():
    results = vector_db.similarity_search("What is differentiation?")
    print(results)


def similarity_with_score():
    results = vector_db.similarity_search_with_score("What is differentiation?")
    doc, score = results[0]
    print(doc, score)


def from_argv():

    # Example inference
    input_text = sys.argv[sys.argv.index("--prompt") + 1]
    inputs = tokenizer(input_text, return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=50)

    print(tokenizer.decode(outputs[0], skip_special_tokens=True))


def rest_api():

    # Create retrieval-augmented chain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm, retriever=vector_db.as_retriever(), return_source_documents=True
    )

    # FastAPI setup
    app = FastAPI()

    class QueryRequest(BaseModel):
        query: str
        chat_history: list = []

    @app.post("/query")
    def query_chatbot(request: QueryRequest):
        try:
            response = qa_chain(
                {"question": request.query, "chat_history": request.chat_history}
            )
            answer = response["answer"]
            sources = [
                {"text": doc.page_content[:200], "source": doc.metadata["source"]}
                for doc in response["source_documents"]
            ]
            return {"answer": answer, "sources": sources}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def with_llm():

    # Load the LLM model
    tokenizer = AutoTokenizer.from_pretrained(
        "deepseek-ai/DeepSeek-R1",
        # torch_dtype=torch.float32,  # Use fp32 for compatibility with MPS)
    )
    model = AutoModelForCausalLM.from_pretrained(
        "deepseek-ai/DeepSeek-R1",
        device_map="auto",
        torch_dtype=torch.float32,  # Use fp32 for compatibility with MPS
        trust_remote_code=True,
    )

    # Use MPS (Metal Performance Shaders) if available
    if torch.backends.mps.is_available():
        print("Using Metal Performance Shaders (MPS)")
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    model = model.to(device)

    llm_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_length=1024,
        temperature=0,
    )
    llm = HuggingFacePipeline(pipeline=llm_pipeline)


def rag_from_docling():
    import json
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain_huggingface import HuggingFaceEndpoint
    from langchain_core.prompts import PromptTemplate

    TOP_K = 3
    GEN_MODEL_ID = "deepseek-ai/DeepSeek-R1"
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

    QUESTION = "Which are the main AI models in Docling?"
    PROMPT = PromptTemplate.from_template(
        "Context information is below.\n---------------------\n{context}\n---------------------\nGiven the context information and not prior knowledge, answer the query.\nQuery: {input}\nAnswer:\n",
    )

    retriever = vector_db.as_retriever(search_kwargs={"k": TOP_K})
    llm = HuggingFaceEndpoint(
        repo_id=GEN_MODEL_ID,
        huggingfacehub_api_token=HF_TOKEN,
        task="text-generation",
    )

    def clip_text(text, threshold=100):
        return f"{text[:threshold]}..." if len(text) > threshold else text

    question_answer_chain = create_stuff_documents_chain(llm, PROMPT)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    resp_dict = rag_chain.invoke({"input": QUESTION})

    clipped_answer = clip_text(resp_dict["answer"], threshold=350)
    print(f"Question:\n{resp_dict['input']}\n\nAnswer:\n{clipped_answer}")
    for i, doc in enumerate(resp_dict["context"]):
        print()
        print(f"Source {i+1}:")
        print(f"  text: {json.dumps(clip_text(doc.page_content, threshold=350))}")
        for key in doc.metadata:
            if key != "pk":
                val = doc.metadata.get(key)
                clipped_val = clip_text(val) if isinstance(val, str) else val
                print(f"  {key}: {clipped_val}")


rag_from_docling()
