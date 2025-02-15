"""
Command-line tools to manage the database and service.
"""

import re
import sys
import os.path
import logging

import click
from flask import Blueprint, current_app

from btcopilot import Engine

_log = logging.getLogger(__name__)


def init_app(app):
    app.cli.add_command(ingest)


def _ensure_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)


DEFAULT_DOCUMENTS_DIR = os.path.realpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "btcopilot-sources",
        "bowentheory",
        "FTiCP Chapters",
    )
)


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


@click.command()
@click.option("--sources-dir", default=DEFAULT_DOCUMENTS_DIR)
@click.option("--data-dir", default=None)
def ingest(sources_dir, data_dir):
    """
    Sync the database with the sources directory.
    """
    _ensure_logging()

    from langchain_community.document_loaders import PyPDFLoader
    from langchain.docstore.document import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    engine = current_app.engine
    if data_dir:
        engine.set_data_dir(data_dir)

    _log.info(f"Loading documents from {sources_dir} into {engine.data_dir()}")

    documents = []
    for file in os.listdir(sources_dir):
        if file.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(sources_dir, file))
            docs = loader.load()
            for doc in docs:
                doc.page_content = normalize_whitespace(doc.page_content)
            chapter_text = " ".join(doc.page_content for doc in docs)
            doc = Document(
                page_content=chapter_text,
                metadata={"source_id": "FTiCP Chapters", "chapter_id": file},
            )
            documents.append(doc)
    if not documents:
        _log.error(f"No documents found in sources directory {sources_dir}")
        return

    _log.info(f"Loaded {len(documents)} chapters into memory.")
    # # For filtering out existing documents
    # # id's are included by default
    # existing_docs = btcopilot.vector_db.db.get(include=[])
    # existing_ids = existing_docs["ids"]

    splits = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=100,
        add_start_index=True,  # track index in original document
    ).split_documents(documents)

    # # Figure out how to use the flask app's engine with custom arguments.
    # with current_app.app_context():
    #     # To set explicit id's for upsert logic
    #     # , ids=[doc.id for doc in documents])
    #     engine = current_app.engine
    engine.vector_db().add_documents(splits)

    _log.info(f"{len(splits)} document splits ingested and stored.")


# def update_from_sources_dir()
# def list_conversations()
