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
    DATA_MODEL_DEFINITIONS,
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
    data_model_prompt = DATA_MODEL_DEFINITIONS

    if hasattr(g, "custom_prompts"):
        role_prompt = g.custom_prompts.get("ROLE_COACH_NOT_THERAPIST", role_prompt)
        bowen_prompt = g.custom_prompts.get(
            "BOWEN_THEORY_COACHING_IN_A_NUTSHELL", bowen_prompt
        )
        data_model_prompt = g.custom_prompts.get(
            "DATA_MODEL_DEFINITIONS", data_model_prompt
        )

    meta_prompt = textwrap.dedent(
        f"""
        {role_prompt}

        **Data Model Definitions**

        {data_model_prompt}

        **Instructions**

        Your goal is to systematically build a complete three-generation family
        diagram by collecting concrete structural data.

        {bowen_prompt}

        **Where are you in data collection?** Review the conversation history
        and check what structural data you have:

        **Required Data (check what's missing):**
        - Parents: Both names? Both ages? Alive/deceased? Together/separated?
        - Siblings: How many? All names? All ages?
        - Maternal grandparents: Both names? Ages or death dates?
        - Paternal grandparents: Both names? Ages or death dates?
        - Problem timeline: When did their issue start (at least year)?

        **Your next response (2-3 sentences):**
        1. Brief acknowledgment of what they just said (show you're listening)
        2. Ask for the next concrete data point you need from the checklist above
        3. Keep it conversational but factual: "Got it. What's your mom's name
           and how old is she?"

        **NEVER use these phrases**:
        - "It sounds like..." / "That sounds..."
        - "It makes sense that you're feeling..."
        - "That must be hard/frustrating/difficult"
        - "How does that make you feel?"
        - "Tell me more" (too vague - ask for specific facts)
        - "How do you think..." (interpretive - just get facts)

        **Response style**:
        - Direct factual questions: "What's your dad's name?" not "Tell me
          about your dad"
        - Always ask for concrete information: names, ages, dates, relationships
        - Sound like a friendly intake coordinator, not a therapist
        - Move systematically through the family structure
        - Don't get stuck exploring feelings or incidents - get the facts

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
    """
    Generate a response from the AI based on the conversation history and the
    meta prompt.
    """
    ai_response = llm.submit_one(LLMFunction.Respond, meta_prompt, temperature=0.45)
    return ai_response.strip()
