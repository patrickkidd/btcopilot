import os.path

from flask import current_app


class Chroma:
    def __init__(self, app=None):
        self.client = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        persist_path = app.config.get("CHROMA_PERSIST_PATH")
        if not persist_path:
            return

        import chromadb

        if persist_path and os.path.exists(persist_path):
            client = chromadb.PersistentClient(path=persist_path)
        else:
            client = chromadb.Client()  # In-memory for quick testing

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["chroma"] = client

    def similarity_search_with_score(self, question: str, k: int):
        client = current_app.extensions["chroma"]
        collection = client.get_or_create_collection(name="chat_messages")
        results = collection.query(
            query_texts=[question], n_results=k, include=["distances"]
        )
        if results["ids"][0]:
            return list(zip(results["documents"][0], results["distances"][0]))
        else:
            return []
