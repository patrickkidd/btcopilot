# Backend for Family Diagram and Bowen theory expert chatbot

This file provides essential project context for Claude Code when working on the
Bowen Theory chatbot app AI training auditing system and licensing and billing
backend for the Family Diagram app.

## Domain Context

See [doc/specs/BOWEN_THEORY.md](doc/specs/BOWEN_THEORY.md) for Bowen theory constructs, SARF variables, data model hierarchy, domain constraints, and error prioritization.

## Auditing System Architecture

### CRITICAL INVARIANT: Source Isolation

**Each coding source (AI or human auditor) must be completely isolated from every other source.**

When viewing a specific source's codes:
- Show ONLY that source's deltas and cumulative PDP
- Statements without data from that source show as empty
- NEVER fall back to AI data when viewing an auditor
- NEVER mix data between auditors

This ensures the logical chain of PDP deltas remains coherent per source. Each source's
cumulative notes column represents their independent interpretation of the conversation,
not a hybrid view.

### AuditFeedback Data Model
```python
class AuditFeedback(db.Model, ModelMixin):
    """Stores audit feedback from domain experts on AI responses"""
    __tablename__ = 'feedback'

    message_id = Column(Integer, ForeignKey('chat_messages.id'), nullable=False)
    auditor_id = Column(String(100), nullable=False)
    feedback_type = Column(String(20), nullable=False)  # 'conversation' or 'extraction'
    thumbs_down = Column(Boolean, default=False)
    comment = Column(Text, nullable=True)
    edited_extraction = Column(JSON, nullable=True)

    # Relationships
    statement = relationship("Statement", backref='feedback')
```

### Ground Truth Approval Workflow

**Key Principle**: GT is what the human says the AI *should have extracted* from what was said - not the "true" facts about the family.

**Mutual Exclusivity Rule**: Only ONE approval per statement is allowed:
- Either the AI extraction is approved (`Statement.approved = True`)
- OR one auditor's correction is approved (`Feedback.approved = True`)
- NEVER both

**Approval Paths**:
1. **Approve AI Extraction**: `POST /training/admin/approve-statement`
   - Sets `Statement.approved = True`
   - Unapproves all feedback for that statement

2. **Approve Auditor Correction**: `POST /training/admin/quick-approve`
   - Sets `Feedback.approved = True`
   - Unapproves statement and all other feedback

**Data Flow**:
- AI generates `Statement.pdp_deltas` (SARF codes) per statement
- Auditors review and optionally correct via `Feedback.edited_extraction`
- Admin approves either AI or auditor version as ground truth
- Approved data used for F1 metrics and export
