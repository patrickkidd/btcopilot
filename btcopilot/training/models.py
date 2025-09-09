"""
Training data models for AI auditing web application.

These models are designed to work with any SQLAlchemy database session
provided by the parent application. No direct database dependencies.

All models are placeholders for Phase 2 - will be implemented in Phase 3.
"""

# Placeholder models - will be implemented in Phase 3
class Statement:
    """Statement model placeholder for Phase 2."""
    pass


class Discussion:
    """Discussion model placeholder for Phase 2."""
    pass


class Speaker:
    """Speaker model placeholder for Phase 2."""
    pass


class SpeakerType:
    """SpeakerType enum placeholder for Phase 2."""
    pass


class Feedback:
    """Feedback model placeholder for Phase 2."""
    pass


# Export all models for easy import
__all__ = [
    'Statement',
    'Discussion', 
    'Speaker',
    'SpeakerType',
    'Feedback'
]