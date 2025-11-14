import os
import time
import enum
import json
from functools import lru_cache
import logging

import pydantic_ai

_log = logging.getLogger(__name__)


class LLMFunction(enum.StrEnum):
    """
    Indentify which models are best for which task, balancing
    accuracy/performance with cost.
    """

    General = "general"

    # Identify data in a chat message
    JSON = "json"

    # Identify whether to segue into talking about data, or continue with a
    # user's current topic
    Direction = "direction"

    # Generate both long or short summaries
    Summarize = "summarize"

    # Generate responses that look and feel like a (good) therapist
    Respond = "respond"

    PDP = "pdp"  # Pending Data Pool, used to detect data points in chat messages

    Arrange = "arrange"


def _markdown_json_2_json(markdown_json: str) -> str:
    return markdown_json.replace("```json", "").replace("```", "")


class LLM:
    """
    Really just here to cache the clients.
    """

    @lru_cache(maxsize=1)  # Thread-safe due to lru_cache
    def _minilm(self):
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("MINILM_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        return SentenceTransformer(model_name)

    @lru_cache(maxsize=1)  # Thread-safe due to lru_cache
    def _openai(self):
        import openai

        return openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def ollama(self, prompt: str, **kwargs) -> str:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            _log.debug(f"Starting ollama request")
            async with session.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3:instruct",
                    "prompt": prompt,
                    **kwargs,
                },  # , "stream": False},
            ) as response:
                _log.debug(
                    f"Completed response w/ status code {response.status} in {time.time() - start_time} seconds"
                )
                full_response = ""
                count = 0
                async for line in response.content:  # Stream NDJSON lines
                    count += 1
                    _log.debug(f"Received line {count}")
                    if line.strip():  # Skip empty lines
                        data = json.loads(line)
                        if "response" in data:  # Check if this chunk contains text
                            full_response += data["response"]
                        if data.get("done", False):  # Exit when generation is complete
                            break

                _log.debug(f"Finished getting {count} lines of ndjson")
                cleaned_response = _markdown_json_2_json(full_response)
                _log.debug(cleaned_response)
                return cleaned_response

    async def openai(self, prompt: str = None, response_format=None, **kwargs) -> str:
        start_time = time.time()
        # _log.debug(f"Starting OpenAI request")
        if response_format:
            from pydantic_ai import Agent
            from pydantic_ai.models.openai import OpenAIModel
            from pydantic_ai.providers.openai import OpenAIProvider

            model = OpenAIModel(
                "gpt-4o-mini",
                provider=OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"]),
            )
            agent = Agent(model, system_prompt=prompt, output_type=response_format)
            response = await agent.run(prompt)
            content = response.output
        else:
            if not "messages" in kwargs:
                kwargs["messages"] = [{"role": "system", "content": prompt}]
            response = await self._openai().chat.completions.create(
                model="gpt-4o-mini",
                stream=False,
                response_format=response_format,
                **kwargs,
            )
            content = response.choices[0].message.content
        _log.debug(
            f"Completed response w/ status code in {time.time() - start_time} seconds"
        )
        _log.debug(f"llm.openai(): --> \n\n{content}")
        return content

    async def submit(self, llm_type: LLMFunction, prompt: str = None, **kwargs):
        if llm_type == LLMFunction.JSON:
            # return await ollama_rest(prompt, **kwargs)
            return await self.openai(prompt, **kwargs)
        elif llm_type in (
            LLMFunction.Direction,
            LLMFunction.Respond,
            LLMFunction.Summarize,
            LLMFunction.PDP,
        ):
            # return await ollama_rest(prompt, **kwargs)
            return await self.openai(prompt, **kwargs)
        else:
            return await self.openai(prompt, **kwargs)

    #     if llm_type == LLMFunction.Direction:
    #         client = self._openai()
    #         model_name = current_app.config["OPENAI_DIRECTION_MODEL"]
    #         messages = [{"role": "user", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     elif llm_type == LLMFunction.JSON:
    #         # return await ollama_rest(prompt, **kwargs)
    #         return await openai_rest(self._openai(), prompt, **kwargs)

    #     elif llm_type == LLMFunction.Summarize:
    #         client = self._openai()
    #         messages = [{"role": "system", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     elif llm_type == LLMFunction.Respond:
    #         client = self._openai()
    #         messages = [{"role": "system", "content": prompt}]
    #         response = client.chat.completions.create(
    #             model=model_name, messages=messages, **kwargs
    #         )
    #         return response.choices[0].message.content

    #     else:
    #         raise ValueError(f"Unknown LLM type: {llm_type}")

    def submit_one(self, llm_type: LLMFunction, prompt: str, **kwargs) -> str:
        """
        Submit a single LLM request and return the response.
        This is a synchronous version of submit, for use in places where
        async is not available.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in current thread, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.submit(llm_type, prompt, **kwargs))
