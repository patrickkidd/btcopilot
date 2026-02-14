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

    # Build structured conversation turns before adding new statement to session
    system_instruction = CONVERSATION_FLOW_PROMPT
    if hasattr(g, "custom_prompts"):
        system_instruction = g.custom_prompts.get(
            "CONVERSATION_FLOW_PROMPT", system_instruction
        )

    turns = []
    for s in discussion.statements:
        role = (
            "model" if s.speaker_id == discussion.chat_ai_speaker_id else "user"
        )
        turns.append((role, s.text))
    turns.append(("user", user_statement))

    statement = Statement(
        discussion_id=discussion.id,
        text=user_statement,
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
        pdp_deltas=asdict(pdp_deltas) if pdp_deltas else None,
    )
    db.session.add(statement)

    ai_response = _generate_response(system_instruction, turns)
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
    system_instruction: str, turns: list[tuple[str, str]]
) -> str:
    ai_response = llm.submit_one(
        LLMFunction.Respond,
        system_instruction=system_instruction,
        turns=turns,
        temperature=0.45,
    )
    return ai_response.strip()
