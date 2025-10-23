"""
Command-line tools to manage the database and service.
"""

import sys
import re
import os.path
import logging
import hashlib

import click

from btcopilot.pro.copilot import Engine
from btcopilot.pro.copilot.splitting import split_markdown_semantically

_log = logging.getLogger(__name__)


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def doc_id(text):
    return hashlib.md5(text.encode()).hexdigest()


@click.command()
@click.option("--sources-dir", default=None)
@click.option("--data-dir", default=None)
def ingest(sources_dir, data_dir):
    """
    Sync the database with the sources directory.
    """

    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain_core.documents import Document
    from langchain_text_splitters import (
        RecursiveCharacterTextSplitter,
        MarkdownTextSplitter,
    )

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    if data_dir is None:
        data_dir = os.path.join(os.getcwd(), "vector_db")
    engine = Engine(data_dir)

    entries = []
    if sources_dir:
        _log.info(f"Loading documents from {sources_dir} into {engine.data_dir()}")

        for file in os.listdir(sources_dir):
            if file.endswith(".pdf"):
                entries.append(
                    {
                        "path": os.path.join(sources_dir, file),
                        "title": file,
                        "authors": [],
                    }
                )
    else:
        _log.info(f"Loading documents from default corpus into {engine.data_dir()}")
        from btcopilot.index import INDEX
        from pathlib import Path

        entries = INDEX

        # Adjust paths relative to this file when called from btcopilot
        for entry in entries:
            entry["path"] = str(Path(__file__).parent.parent / entry["path"])

    documents = []
    for entry in entries:
        fpath = entry["path"]
        _log.info(f"Reading {fpath}...")

        if fpath.endswith(".pdf"):
            loader = PyPDFLoader(entry["path"])
            docs = loader.load()
            for doc in docs:
                doc.page_content = normalize_whitespace(doc.page_content)
            docs = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                add_start_index=True,  # track index in original document
            ).split_documents(docs)
        elif fpath.endswith(".md"):
            docs = [
                Document(page_content=x)
                for x in split_markdown_semantically(file_path=fpath)
            ]
        else:
            raise ValueError(f"Unsupported file type: {entry['path']}")
        for doc in docs:
            doc.metadata["fd_file_name"] = fpath
            doc.metadata["fd_title"] = entry["title"]
            doc.metadata["fd_authors"] = ",".join(entry["authors"])
        # file_text = " ".join(doc.page_content for doc in docs)
        # doc = Document(
        #     page_content=file_text,
        #     metadata={
        #         "title": entry["title"],
        #         "authors": ",".join(entry["authors"]),
        #     },
        # )
        documents.extend(docs)
        # ids.append(doc_id(doc.page_content))
    if not documents:
        _log.error(f"No documents found in sources directory {sources_dir}")
        return

    _log.info(f"Read {len(documents)} files into memory, loading into vector db...")
    # # For filtering out existing documents
    # # id's are included by default
    # existing_docs = btcopilot.vector_db.db.get(include=[])
    # existing_ids = existing_docs["ids"]

    # # Figure out how to use the flask app's engine with custom arguments.
    # with current_app.app_context():
    #     # To set explicit id's for upsert logic
    #     # , ids=[doc.id for doc in documents])
    #     engine = current_app.engine
    engine.vector_db().add_documents(documents)

    _log.info(f"{len(documents)} document splits ingested and stored.")


# def update_from_sources_dir()
# def list_conversations()
