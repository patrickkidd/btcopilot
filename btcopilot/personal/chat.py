import enum
import textwrap
import logging

from dataclasses import dataclass, asdict
from flask import g

from btcopilot.extensions import db, ai_log, llm, LLMFunction
from btcopilot.async_utils import gather
from btcopilot.personal import pdp
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import DiagramData, PDP
from btcopilot.personal.prompts import (
    ROLE_COACH_NOT_THERAPIST,
    BOWEN_THEORY_COACHING_IN_A_NUTSHELL,
    DATA_MODEL_DEFINITIONS,
)


_log = logging.getLogger(__name__)


@dataclass
class Response:
    statement: str
    pdp: PDP | None = None


class ResponseDirection(enum.StrEnum):
    Lead = "lead"
    Follow = "follow"


async def detect_response_direction(
    user_statement: str, discussion: Discussion
) -> ResponseDirection:
    s_statement = [x.text for x in discussion.statements]
    # Leaving "therapist" in there since this just has binary output.
    direction_prompt = textwrap.dedent(
        f"""
        You are an AI therapist chatbot. Determine whether the person who wrote the
        following chat prompt is implying that they want you to follow the topic they
        are laying down, or not. If they did not indicate either way, assume you should lead.
        Return only a single string of either "follow" or "lead".

        USER_MESSAGE: {user_statement}

        THREAD MESSAGES: {s_statement}
        """
    )
    direction = await llm.submit(LLMFunction.Direction, direction_prompt)
    if direction == "follow":
        return ResponseDirection.Follow
    else:
        return ResponseDirection.Lead


def ask(discussion: Discussion, user_statement: str) -> Response:

    ai_log.info(f"User statement: {user_statement}")
    if discussion.diagram:
        diagram_data = discussion.diagram.get_diagram_data()
    else:
        diagram_data = DiagramData()
    results = gather(
        pdp.update(discussion, diagram_data, user_statement),
        detect_response_direction(user_statement, discussion),
    )

    (new_pdp, pdp_deltas), response_direction = results
    ai_log.info(f"Response direction: {response_direction}")

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
    data_model_prompt = DATA_MODEL_DEFINITIONS

    if hasattr(g, "custom_prompts"):
        role_prompt = g.custom_prompts.get("ROLE_COACH_NOT_THERAPIST", role_prompt)
        bowen_prompt = g.custom_prompts.get(
            "BOWEN_THEORY_COACHING_IN_A_NUTSHELL", bowen_prompt
        )
        data_model_prompt = g.custom_prompts.get(
            "DATA_MODEL_DEFINITIONS", data_model_prompt
        )

    ORIENTATION_FRAGMENT = textwrap.dedent(
        f"""
        {role_prompt}
        
        **Data Model Definitions**

        {data_model_prompt}
        """
    )

    if response_direction == ResponseDirection.Lead:

        meta_prompt = textwrap.dedent(
            f"""
            {ORIENTATION_FRAGMENT}

            **Instructions**
            
            Generate a curious and engaging response to the following chat
            conversation history and last user statement. Work backward from the
            stated symptom or problem in a way that can illuminate the following
            stack of basic information, more or less in the following order:

            {bowen_prompt}

            Once a reasonable amount of information is gathered from the above,
            there may be some fluidity about what area in the stack to focus on.

            **Conversation History**

            {discussion.conversation_history()}

            **Last User Statement**

            {user_statement}
            """
        )

    elif response_direction == ResponseDirection.Follow:

        meta_prompt = textwrap.dedent(
            f"""
            {ORIENTATION_FRAGMENT}
            
            **Instructions**
            
            Consider the following statement history and generate your next
            response being curious about what they just said in their last user
            statement. This is less about data collection now and more about
            following the discussion they are providing. Stay away from the usual
            canned "Can you tell me more?" or other typical therapist-ish
            responses. Remember, you are not a therapist, but an expert at
            correlating the four main variables to understand how the person's
            threat response (anxiety variable) in relation to positive and
            negative shifts relationships (relationship variable) gets in
            peoples' way toward their goals (problem or symptom variable).

            **Conversation History**

            {discussion.conversation_history()}

            **Last User Statement**

            {user_statement}
            """
        )

    else:
        raise ValueError(f"Unknown response direction: {response_direction}")

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
    """
    Generate a response from the AI based on the conversation history and the
    meta prompt.
    """
    ai_response = llm.submit_one(LLMFunction.Respond, meta_prompt, temperature=0.45)
    return ai_response.strip()
