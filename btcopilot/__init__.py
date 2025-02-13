from langchain_huggingface import HuggingFaceEmbeddings

# from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_DB_DIR = "./data"
LLM_MODEL = "mistral"


# embeddings = OllamaEmbeddings(
#     # model_name=EMBEDDINGS_MODEL
#     model_name="nomic-embed-text"
# )

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)

vector_db = Chroma(
    collection_name="btcopilot",
    persist_directory=VECTOR_DB_DIR,
    embedding_function=embeddings,
)
print(f"Loaded btcopilot vector db from {VECTOR_DB_DIR}")
