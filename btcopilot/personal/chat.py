import textwrap
import logging

from dataclasses import dataclass
from flask import g

from btcopilot.extensions import db, ai_log, llm, LLMFunction
from btcopilot.async_utils import one_result
from btcopilot import pdp
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import DiagramData, PDP, asdict
from btcopilot.personal.prompts import (
    ROLE_COACH_NOT_THERAPIST,
    BOWEN_THEORY_COACHING_IN_A_NUTSHELL,
)


_log = logging.getLogger(__name__)


@dataclass
class Response:
    statement: str
    pdp: PDP | None = None


def ask(discussion: Discussion, user_statement: str) -> Response:

    ai_log.info(f"User statement: {user_statement}")
    if discussion.diagram:
        diagram_data = discussion.diagram.get_diagram_data()
    else:
        diagram_data = DiagramData()

    new_pdp, pdp_deltas = one_result(
        pdp.update(discussion, diagram_data, user_statement)
    )

    # Write to disk
    diagram_data.pdp = new_pdp
    if discussion.diagram:
        discussion.diagram.set_diagram_data(diagram_data)

    statement = Statement(
        discussion_id=discussion.id,
        text=user_statement,
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
        pdp_deltas=asdict(pdp_deltas) if pdp_deltas else None,
    )
    db.session.add(statement)

    # Get the llm to generate a human-like response according to the direction
    # of the conversation and the context. Otherwise we would just have the same
    # canned response for each mode

    # Check for custom prompts in g context (used for testing)
    role_prompt = ROLE_COACH_NOT_THERAPIST
    bowen_prompt = BOWEN_THEORY_COACHING_IN_A_NUTSHELL

    if hasattr(g, "custom_prompts"):
        role_prompt = g.custom_prompts.get("ROLE_COACH_NOT_THERAPIST", role_prompt)
        bowen_prompt = g.custom_prompts.get(
            "BOWEN_THEORY_COACHING_IN_A_NUTSHELL", bowen_prompt
        )

    meta_prompt = textwrap.dedent(
        f"""
        {role_prompt}

        **Instructions**

        Your goal is to first thoroughly understand the presenting problem, then
        pivot to systematically collecting family structure data for a
        three-generation diagram.

        {bowen_prompt}

        **Your next response (2-3 sentences):**
        1. Brief acknowledgment (a word or two, not restating what they said)
        2. Ask for the next missing data point from the current phase
        3. If pivoting from problem to family: "OK, I have a good picture of
           what's going on. Now let me get some family background. What's your
           mom's name and how old is she?"

        **Do NOT parrot back what the user just said.** Move the conversation forward.

        **Conversation History**

        {discussion.conversation_history()}

        **Last User Statement**

        {user_statement}
        """
    )

    ai_response = _generate_response(discussion, diagram_data, meta_prompt)
    ai_log.info(f"AI response: {ai_response}")

    response = Response(
        statement=ai_response,
        pdp=diagram_data.pdp,
    )
    ai_statement = Statement(
        discussion_id=discussion.id,
        text=ai_response,
        speaker=discussion.chat_ai_speaker,
        order=discussion.next_order(),  # AI response comes after user statement
    )
    db.session.add(ai_statement)
    return response


def _generate_response(
    discussion: Discussion, diagram_data: DiagramData, meta_prompt: str
) -> str:
    ai_response = llm.submit_one(LLMFunction.Respond, meta_prompt, temperature=0.45)
    return ai_response.strip()
