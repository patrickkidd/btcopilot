import os
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain.docstore.document import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import btcopilot

DOCUMENTS_DIR = os.path.join("btcopilot-sources", "bowentheory", "FTiCP Chapters")


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def ingest():

    documents = []
    for file in os.listdir(DOCUMENTS_DIR):
        if file.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(DOCUMENTS_DIR, file))
            docs = loader.load()
            for doc in docs:
                doc.page_content = normalize_whitespace(doc.page_content)
            chapter_text = " ".join(doc.page_content for doc in docs)
            doc = Document(
                page_content=chapter_text,
                metadata={"source_id": "FTiCP Chapters", "chapter_id": file},
            )
            documents.append(doc)
    print(f"Loaded {len(documents)} chapters into memory.")

    # # For filtering out existing documents
    # # id's are included by default
    # existing_docs = btcopilot.vector_db.db.get(include=[])
    # existing_ids = existing_docs["ids"]

    splits = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=100,
        add_start_index=True,  # track index in original document
    ).split_documents(documents)

    # To set explicit id's for upsert logic
    # , ids=[doc.id for doc in documents])
    btcopilot.vector_db.add_documents(splits)
    print(f"{len(splits)} document splits ingested and stored.")


if __name__ == "__main__":
    ingest()
