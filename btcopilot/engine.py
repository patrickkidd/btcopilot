# from cachetools import TTLCache
import os.path
import logging
from dataclasses import dataclass

from btcopilot import EMBEDDINGS_MODEL, LLM_MODEL

_log = logging.getLogger(__name__)


@dataclass
class Response:
    answer: str
    sources: list[dict]


class Engine:
    """
    The resource-intensive part of the app. Can be shared across tests if necessary.
    """

    def __init__(self, data_dir: str):
        self._llm = None
        self._vector_db = None
        self._data_dir = data_dir
        # self._conversation_chains = TTLCache(maxsize=1000, ttl=3600)

    def data_dir(self) -> str:
        return self._data_dir

    def set_data_dir(self, data_dir: str):
        if self._llm or self._vector_db:
            raise RuntimeError("Cannot change engine data_dir after initialization")
        self._data_dir = data_dir

    def llm(self):
        if not self._llm:
            from langchain_ollama import OllamaLLM

            self._llm = OllamaLLM(model="mistral", temperature=0)
            _log.info(f"Created LLM using {LLM_MODEL}")
        return self._llm

    def vector_db(self):
        if not self._vector_db:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_chroma import Chroma

            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
            self._vector_db = Chroma(
                collection_name="btcopilot",
                persist_directory=self.data_dir(),
                embedding_function=embeddings,
            )
            _log.info(f"Loaded vector db from {self.data_dir()}")
        return self._vector_db

    def ask(self, question: str) -> Response:
        from langchain.prompts import ChatPromptTemplate

        PROMPT_TEMPLATE = """
    Ansert the following question based only on the following context: {context}

    ---

    Answer the question based on the above context: {question}
    """
        NUM_RESULTS = 5

        doc_results = self.vector_db().similarity_search_with_score(
            question, k=NUM_RESULTS
        )
        _log.info(f"Using {len(doc_results)} matching results.")

        context_text = "\n\n---\n\n".join(
            [doc.page_content for doc, _score in doc_results]
        )
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=question)
        response_text = self.llm().invoke(prompt)
        sources = [
            {
                "source": doc.metadata.get("chapter_id", None),
                "passage": doc.page_content,
            }
            for doc, _score in doc_results
        ]
        response = Response(answer=response_text, sources=sources)
        self._on_response(response)
        return response

    def _on_response(self, response: Response):
        """mock for tests"""


# from langchain_ollama import OllamaEmbeddings
# embeddings = OllamaEmbeddings(
#     # model_name=EMBEDDINGS_MODEL
#     model_name="nomic-embed-text"
# )


# retreiver = vector_db.as_retriever()
# from langchain.chains import ConversationalRetrievalChain
# from langchain.memory import ConversationBufferMemory
# from langchain_community.chat_message_histories import SQLChatMessageHistory


#         if conversation_id is None:  # New thread
#             chat_memory = SQLChatMessageHistory(
#                 connection_string=str(db.engine.url), conversation_id=conversation_id
#             )
#             memory = ConversationBufferMemory(
#                 chat_memory=chat_memory, return_messages=True
#             )
#             chain = ConversationalRetrievalChain.from_llm(llm, retriever, memory=memory)
#             conversation_id = uuid.uuid()
#             chain.conversation_id = conversation_id
#             conversation_chains[conversation_id] = chain
