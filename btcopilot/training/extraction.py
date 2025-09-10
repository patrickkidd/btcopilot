"""
Training data extraction utilities.

Handles background processing of statements for training data collection,
including finding next statements to process and running extraction jobs.
"""

import logging
import asyncio
import nest_asyncio
from sqlalchemy import create_engine
from flask import current_app

from ..extensions import db
from .models import Discussion, Statement, Speaker, SpeakerType

_log = logging.getLogger(__name__)


def _next_statement() -> Statement:
    """Find the next statement that needs processing for extraction."""
    # Get all subject statements from discussions marked for extraction
    candidates = (
        Statement.query.join(Speaker)
        .join(Discussion, Statement.discussion_id == Discussion.id)
        .filter(
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
            Discussion.extracting == True,
        )
        .order_by(
            Statement.discussion_id.asc(),
            Statement.order.asc(),
            Statement.id.asc(),  # Tiebreaker for statements with same order
        )
        .all()
    )

    # Find the first one that actually needs processing
    # Check for None or empty dict since SQLAlchemy JSON column filters are unreliable
    for stmt in candidates:
        if stmt.pdp_deltas is None or stmt.pdp_deltas == {}:
            return stmt

    return None


def extract_next_statement(*args, **kwargs):
    """
    Background job to extract data from the oldest pending Subject statement.
    Returns True if a statement was processed, False if no statements are pending.
    
    This function is designed to work with both standalone btcopilot and
    fdserver integration.
    """
    _log.info(f"extract_next_statement() called with: args: {args}, kwargs: {kwargs}")

    try:
        try:
            db.session.get_bind()
        except:
            engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
            db.session.bind = engine

        # Find next statement to process
        statement = _next_statement()

        if not statement:
            _log.debug("No pending statements found")
            return False

        _log.info(
            f"Processing statement {statement.id} (speaker: {statement.speaker.type}, text: '{statement.text[:50]}...') from discussion {statement.discussion_id}"
        )

        discussion = statement.discussion
        if not discussion:
            _log.warning(
                f"Skipping statement {statement.id} - missing discussion"
            )
            return False

        # Try to import and use fdserver's extraction logic if available
        try:
            from fdserver.therapist.database import Database
            from fdserver.therapist import pdp
            
            # Get or create diagram database
            if hasattr(discussion, 'diagram') and discussion.diagram:
                database = discussion.diagram.get_database()
            else:
                database = Database()

            try:
                # Apply nest_asyncio to allow nested event loops in Celery workers
                nest_asyncio.apply()

                # Run pdp.update for this statement
                new_pdp, pdp_deltas = asyncio.run(
                    pdp.update(discussion, database, statement.text)
                )

                # Update database and statement
                database.pdp = new_pdp
                if hasattr(discussion, 'diagram') and discussion.diagram:
                    discussion.diagram.set_database(database)
                if pdp_deltas:
                    statement.pdp_deltas = pdp_deltas.model_dump()
                    _log.info(
                        f"Stored PDP deltas on statement {statement.id}: {len(pdp_deltas.events)} events, {len(pdp_deltas.people)} people"
                    )
                else:
                    statement.pdp_deltas = None
                    _log.info(f"No PDP deltas generated for statement {statement.id}")

            except Exception as e:
                _log.error(f"Error in PDP extraction: {e}", exc_info=True)
                # Set empty deltas to mark as processed
                statement.pdp_deltas = {}
                
        except ImportError:
            # fdserver not available, mark as processed with empty deltas
            _log.info("fdserver not available, marking statement as processed")
            statement.pdp_deltas = {}

        # Check if there are any more unprocessed statements in this discussion
        remaining_candidates = (
            Statement.query.join(Speaker)
            .filter(
                Speaker.type == SpeakerType.Subject,
                Statement.text.isnot(None),
                Statement.text != "",
                Statement.discussion_id == discussion.id,
                Statement.id != statement.id,  # Exclude the current statement
            )
            .all()
        )

        # Count how many actually need processing
        remaining_statements = sum(
            1
            for s in remaining_candidates
            if s.pdp_deltas is None or s.pdp_deltas == {}
        )

        # If no more statements to process in this discussion, set extracting to False
        if remaining_statements == 0:
            discussion.extracting = False
            _log.info(
                f"Extraction complete for discussion {discussion.id}, setting extracting=False"
            )
        else:
            _log.info(f"More statements remain for discussion {discussion.id}")

        # Commit this statement's updates
        db.session.commit()

        _log.info(
            f"Extracted data from statement {statement.id} for discussion {discussion.id}"
        )
        return True

    except Exception as e:
        _log.error(
            f"Error processing statement {statement.id if 'statement' in locals() else None}: {e}",
            exc_info=True,
        )
        # Roll back this statement's transaction
        db.session.rollback()
        return False