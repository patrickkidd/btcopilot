import logging

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.tests.personal.synthetic import (
    ConversationSimulator,
    DEPRECATED_PERSONAS,
)
from btcopilot.personal.chat import ask


_log = logging.getLogger(__name__)


def generate_synthetic_discussion(
    self,
    persona_id_or_name,
    username: str,
    max_turns: int,
):
    _log.info(
        f"generate_synthetic_discussion() persona={persona_id_or_name}, user={username}, "
        f"max_turns={max_turns}"
    )

    persona_id = None

    if isinstance(persona_id_or_name, int):
        from btcopilot.personal.models import SyntheticPersona

        db_persona = db.session.get(SyntheticPersona, persona_id_or_name)
        if not db_persona:
            raise ValueError(f"SyntheticPersona not found: {persona_id_or_name}")
        persona = db_persona.to_persona()
        persona_id = persona_id_or_name
    else:
        persona = next(
            (p for p in DEPRECATED_PERSONAS if p.name == persona_id_or_name), None
        )
        if not persona:
            raise ValueError(f"Persona not found: {persona_id_or_name}")

    from btcopilot.personal.models import DiscussionStatus

    simulator = ConversationSimulator(
        max_turns=max_turns,
        persist=True,
        username=username,
    )

    def on_progress(turn_num, total, user_text, ai_text):
        self.update_state(
            state="PROGRESS",
            meta={
                "current": turn_num,
                "total": total,
                "user_text": user_text[:100] if user_text else "",
                "ai_text": ai_text[:100] if ai_text else "",
            },
        )

    result = simulator.run(
        persona, ask, on_progress=on_progress, yield_progress=False
    )

    discussion = None
    if result.discussionId:
        discussion = db.session.get(Discussion, result.discussionId)
    if discussion:
        if persona_id:
            discussion.synthetic_persona_id = persona_id
        discussion.status = DiscussionStatus.Ready

    db.session.commit()

    _log.info(
        f"Synthetic discussion {result.discussionId} generated "
        f"({len(result.turns) // 2} turns)"
    )

    return {
        "success": True,
        "discussion_id": result.discussionId,
        "turn_count": len(result.turns) // 2,
        "quality_score": result.quality.score if result.quality else None,
        "coverage_rate": (
            result.coverage.coverageRate if result.coverage else None
        ),
    }
