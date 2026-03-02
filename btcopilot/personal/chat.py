import logging

from dataclasses import dataclass
from flask import g

from btcopilot.extensions import db, ai_log
from btcopilot.llmutil import gemini_text_sync
from btcopilot.personal.models import Discussion, Statement
from btcopilot.personal.prompts import CONVERSATION_FLOW_PROMPT


_log = logging.getLogger(__name__)


@dataclass
class Response:
    statement: str


def ask(discussion: Discussion, user_statement: str) -> Response:

    ai_log.info(f"User statement: {user_statement}")

    # Build structured conversation turns before adding new statement to session
    system_instruction = CONVERSATION_FLOW_PROMPT
    if hasattr(g, "custom_prompts"):
        system_instruction = g.custom_prompts.get(
            "CONVERSATION_FLOW_PROMPT", system_instruction
        )

    turns = []
    for s in discussion.statements:
        role = "model" if s.speaker_id == discussion.chat_ai_speaker_id else "user"
        turns.append((role, s.text))
    turns.append(("user", user_statement))

    statement = Statement(
        discussion_id=discussion.id,
        text=user_statement,
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
    )
    db.session.add(statement)

    ai_response = _generate_response(system_instruction, turns)
    ai_log.info(f"AI response: {ai_response}")

    ai_statement = Statement(
        discussion_id=discussion.id,
        text=ai_response,
        speaker=discussion.chat_ai_speaker,
        order=discussion.next_order(),
    )
    db.session.add(ai_statement)
    return Response(statement=ai_response)


def _generate_response(system_instruction: str, turns: list[tuple[str, str]]) -> str:
    ai_response = gemini_text_sync(
        system_instruction=system_instruction,
        turns=turns,
        temperature=0.45,
    )
    return ai_response.strip()
