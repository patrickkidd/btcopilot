import logging

from dataclasses import dataclass
from flask import g

from btcopilot.extensions import db, ai_log, llm, LLMFunction
from btcopilot.async_utils import one_result
from btcopilot import pdp
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import DiagramData, PDP, asdict
from btcopilot.personal.prompts import CONVERSATION_FLOW_PROMPT


_log = logging.getLogger(__name__)


@dataclass
class Response:
    statement: str
    pdp: PDP | None = None


def ask(
    discussion: Discussion, user_statement: str, skip_extraction: bool = False
) -> Response:

    ai_log.info(f"User statement: {user_statement}")
    if discussion.diagram:
        diagram_data = discussion.diagram.get_diagram_data()
    else:
        diagram_data = DiagramData()

    pdp_deltas = None
    if not skip_extraction:
        new_pdp, pdp_deltas = one_result(
            pdp.update(discussion, diagram_data, user_statement)
        )

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
    conversation_prompt = CONVERSATION_FLOW_PROMPT
    if hasattr(g, "custom_prompts"):
        conversation_prompt = g.custom_prompts.get(
            "CONVERSATION_FLOW_PROMPT", conversation_prompt
        )

    meta_prompt = conversation_prompt.format(
        conversation_history=discussion.conversation_history(),
        user_statement=user_statement,
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
