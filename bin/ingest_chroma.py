import os
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Directories
DOCUMENTS_DIR = "./btcopilot-sources/bowentheory"
VECTOR_DB_DIR = "./data"
HF_EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def normalize_whitespace(text):
    # Replace all sequences of whitespace with a single space
    return re.sub(r"\s+", " ", text).strip()


def load_documents_pypdf(directory):
    documents = []
    for file in os.listdir(directory):
        if file.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(directory, file))
            docs = loader.load_and_split()
            for doc in docs:
                doc.page_content = normalize_whitespace(doc.page_content)
            documents.extend(docs)
    return documents


def load_documents_docling(directory):
    from langchain_docling.loader import ExportType
    from docling.chunking import HybridChunker
    from langchain_docling import DoclingLoader

    documents = []
    for file in os.listdir(directory):
        if file.endswith(".pdf"):

            loader = DoclingLoader(
                file_path=os.path.join(directory, file),
                export_type=ExportType.DOC_CHUNKS,
                chunker=HybridChunker(tokenizer=HF_EMBEDDINGS_MODEL),
            )

            docs = loader.load()

            # docs = loader.load_and_split()
            for doc in docs:
                doc.page_content = normalize_whitespace(doc.page_content)
            documents.extend(docs)
    return documents


# Main ingestion script
def ingest():
    # Load documents
    documents = load_documents_docling(DOCUMENTS_DIR)
    # documents = load_documents_pypdf(DOCUMENTS_DIR)
    print(f"Loaded {len(documents)} documents.")

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=100,
        add_start_index=True,  # track index in original document
    )
    all_splits = text_splitter.split_documents(documents)

    # Generate embeddings
    embeddings = HuggingFaceEmbeddings(model_name=HF_EMBEDDINGS_MODEL)

    # Store embeddings in a vector database
    vector_db = Chroma(
        collection_name="academic_docs",
        persist_directory=VECTOR_DB_DIR,
        embedding_function=embeddings,
    )
    vector_db.add_documents(all_splits)
    print("Documents ingested and stored.")


if __name__ == "__main__":
    ingest()
