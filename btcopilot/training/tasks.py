import logging
import datetime
import asyncio
from datetime import timedelta

import click
from sqlalchemy import create_engine
from flask import current_app

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion
from btcopilot.training.routes.discussions import (
    extract_next_statement as _extract_next_statement,
)
from btcopilot.tests.personal.synthetic import (
    ConversationSimulator,
    DEPRECATED_PERSONAS,
)
from btcopilot.personal.chat import ask


_log = logging.getLogger(__name__)


def extract_next_statement():
    _log.info(f"extract_next_statement() called")

    # Ensure we have a database connection
    try:
        db.session.get_bind()
    except RuntimeError:
        engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
        db.session.bind = engine

    # Close any existing session to ensure fresh data
    db.session.close()

    result = _extract_next_statement()

    # If there are more statements to process, schedule another task
    if result:
        from btcopilot.extensions import celery

        celery.send_task("extract_next_statement", countdown=1)
    else:
        _log.info("No statements pending extraction")

    return result


def extract_discussion_statements(discussion_id: int):
    discussion = Discussion.query.get(discussion_id)
    if not discussion:
        raise ValueError(f"Discussion {discussion_id} not found")

    discussion.extracting = True
    db.session.commit()

    from btcopilot.extensions import celery

    celery.send_task("extract_next_statement")

    _log.info(f"Celery extraction task started - discussion_id: {discussion_id}")
    return True


@click.command("extract-discussion-data")
def extract_discussion_data():
    _log.info(f"extract_discussion_data() {datetime.datetime.now()}")

    result = extract_next_statement()
    if result:
        _log.info("Discussion data extracted, another triggered")
    else:
        _log.info("All discussions extracted.")


def generate_synthetic_discussion(
    self,
    persona_id_or_name,
    username: str,
    max_turns: int,
    skip_extraction: bool,
):
    _log.info(
        f"generate_synthetic_discussion() persona={persona_id_or_name}, user={username}, "
        f"max_turns={max_turns}, skip_extraction={skip_extraction}"
    )

    try:
        persona_id = None

        if isinstance(persona_id_or_name, int):
            # New path: load from DB
            from btcopilot.personal.models import SyntheticPersona

            db_persona = db.session.get(SyntheticPersona, persona_id_or_name)
            if not db_persona:
                raise ValueError(f"SyntheticPersona not found: {persona_id_or_name}")
            persona = db_persona.to_persona()
            persona_id = persona_id_or_name
        else:
            # Legacy path: look up from deprecated personas
            persona = next(
                (p for p in DEPRECATED_PERSONAS if p.name == persona_id_or_name), None
            )
            if not persona:
                raise ValueError(f"Persona not found: {persona_id_or_name}")

        simulator = ConversationSimulator(
            max_turns=max_turns,
            persist=True,
            username=username,
            skip_extraction=skip_extraction,
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

        # Link to SyntheticPersona if available
        if persona_id and result.discussionId:
            discussion = db.session.get(Discussion, result.discussionId)
            if discussion:
                discussion.synthetic_persona_id = persona_id

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

    except Exception as e:
        _log.error(f"Error generating synthetic discussion: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
