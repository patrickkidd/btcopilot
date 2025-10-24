"""
BT Copilot API core

EXPERIMENTATION:
- K (max matched results on query)
- Splitting params
- llm model
"""

# from cachetools import TTLCache

import os
import logging
import time
from dataclasses import dataclass

from langchain_core.messages import AIMessage

from btcopilot.extensions import EMBEDDINGS_MODEL, LLM_MODEL

_log = logging.getLogger(__name__)


PROMPT_TEMPLATE = """
Answer the following question based only on the following academic literature:

QUESTION:
{question}
-------------------------
THEORETICAL LITERATURE:

{literature}
"""

PROMPT_TEMPLATE_WITH_TIMESERIES = """
The following is 1) timeseries data from a family's emotional functioning, 2) a
question about the timeseries, and C) literature containing the concepts used to
evaluate the timeseries. Answer the question about the timeseries using only the
provided academic literature.

-------------------------
TIMESERIES:

{timeseries}
-------------------------
QUESTION:

{question}
-------------------------
THEORETICAL LITERATURE:

{literature}
"""


@dataclass
class Response:
    answer: str
    sources: list[dict]
    vectors_time: float = 0.0
    llm_time: float = 0.0
    total_time: float = 0.0

    def __str__(self):
        return (
            f"Answer: {self.answer}\n"
            f"Sources: {self.sources}\n"
            f"Vector DB Time: {self.vectors_time}\n"
            f"LLM Time: {self.llm_time}\n"
            f"Total Time: {self.total_time}\n"
        )


@dataclass
class Event:
    dateTime: str
    description: str
    people: list[str]
    variables: dict[str, str]


def formatTimelineData(events: list[Event]) -> str:
    timelineData = ""
    for event in events:
        s_variables = ", ".join(f"{k}: {v}" for k, v in event.variables.items())
        timelineData += (
            f"Timestamp: {event.dateTime}\t"
            f"Description: {event.description}\t"
            f"People: {', '.join(event.people)}\t"
            f"Variables: {s_variables}\n"
        )
    return timelineData


class Engine:
    """
    The resource-intensive part of the app. Can be shared across tests if necessary.
    """

    def __init__(self, data_dir: str, k: int = 5):
        self._llm = None
        self._vector_db = None
        self._data_dir = data_dir
        self._k = k
        # self._conversation_chains = TTLCache(maxsize=1000, ttl=3600)

    def data_dir(self) -> str:
        return self._data_dir

    def set_data_dir(self, data_dir: str):
        if self._llm or self._vector_db:
            raise RuntimeError("Cannot change engine data_dir after initialization")
        self._data_dir = data_dir

    def llm(self):
        if not self._llm:
            _log.info(f"Creating LLM using {LLM_MODEL}...")
            # from langchain_ollama import OllamaLLM

            # self._llm = OllamaLLM(model=LLM_MODEL, temperature=0)

            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=LLM_MODEL,
                temperature=0,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
            )
            _log.info(f"Created LLM using {LLM_MODEL}")
        return self._llm

    def invoke_llm(self, question: str) -> str:
        """
        Translate from various return types to a simple string.
        """
        ai_message = self.llm().invoke(question)
        if isinstance(ai_message, AIMessage):
            response_text = ai_message.content
        else:
            response_text = ai_message
        return response_text.strip()

    def vector_db(self):
        if not self._vector_db:
            _log.info(f"Loading vector db from {self.data_dir()}...")
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

    def _chat_template(self, kind):
        """
        Mockable stub
        """
        from langchain_core.prompts import ChatPromptTemplate

        return ChatPromptTemplate.from_template(kind)

    def ask(
        self, question: str, events: list[Event] = None, conversation_id: str = None
    ) -> Response:

        _log.info(f"Query with question: {question}")

        total_start_time = vector_start_time = time.perf_counter()
        doc_results = self.vector_db().similarity_search_with_score(question, k=self._k)
        vector_end_time = time.perf_counter()
        _log.info(f"Using {len(doc_results)} matching results for this query.")

        context_literature = "\n\n---\n\n".join(
            [doc.page_content for doc, _score in doc_results]
        )
        if events:
            _log.info(f"Using {len(events)} timeline events for this query.")
            context_timeseries = formatTimelineData(events)
            prompt_template = self._chat_template(PROMPT_TEMPLATE_WITH_TIMESERIES)
            prompt = prompt_template.format(
                literature=context_literature,
                question=question,
                timeseries=context_timeseries,
            )
        else:
            prompt_template = self._chat_template(PROMPT_TEMPLATE)
            prompt = prompt_template.format(
                literature=context_literature, question=question
            )
        llm_start_time = time.perf_counter()
        response_text = self.invoke_llm(prompt)
        total_end_time = llm_end_time = time.perf_counter()
        sources = [
            {
                "fd_file_name": doc.metadata["fd_file_name"],
                "fd_authors": doc.metadata["fd_authors"],
                "fd_title": doc.metadata["fd_title"],
                "passage": doc.page_content,
            }
            for doc, _score in doc_results
        ]
        _log.info(f"Response: {response_text}")
        response = Response(
            answer=response_text,
            sources=sources,
            vectors_time=(vector_end_time - vector_start_time),
            llm_time=(llm_end_time - llm_start_time),
            total_time=(total_end_time - total_start_time),
        )
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
# from langchain_community.chat_message_histories import SQLStatementHistory


#         if conversation_id is None:  # New discussion
#             chat_memory = SQLStatementHistory(
#                 connection_string=str(db.engine.url), conversation_id=conversation_id
#             )
#             memory = ConversationBufferMemory(
#                 chat_memory=chat_memory, return_messages=True
#             )
#             chain = ConversationalRetrievalChain.from_llm(llm, retriever, memory=memory)
#             conversation_id = uuid.uuid()
#             chain.conversation_id = conversation_id
#             conversation_chains[conversation_id] = chain
