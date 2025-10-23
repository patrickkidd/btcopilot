# Backend for Family Diagram and Bowen theory expert chatbot

This file provides essential project context for Claude Code when working on the
Bowen Theory chatbot app AI training auditing system and licensing and billing
backend for the Family Diagram app.

## Project Vision & Goals

### Primary Objective
Build a scalable web-based auditing system where domain experts (5-10 initially)
provide feedback on:
1. **Data extraction accuracy** - How well the AI extracts Bowen Theory
   constructs from conversations
2. **Conversational flow quality** - How well the AI maintains appropriate
   therapeutic coaching style

### Current Challenge
Manual feedback review is unsustainable - need to move from
data-point-by-data-point analysis to automated aggregation and prioritization
while preserving domain expertise in decision-making.

### Strategic Approach
- **Short-term**: Scale prompt engineering through automated feedback analysis
- **Long-term**: Prepare dataset for fine-tuning when resources/data volume permit
- **Hybrid**: Build reusable feedback dataset that supports both approaches

## Domain Context: Bowen Theory

### Core Constructs (Priority Order for Errors)
1. **Functioning** - The independent variable; ability to balance emotion and intellect
2. **Triangle** - Two people align (inside) against a third (outside) to reduce discomfort
3. **ChildFocus** - Attention to real/perceived problem in a child (single child recipient)
4. **Distance** - Avoiding open communication up to cutoff in extreme
5. **Conflict** - Overt arguments up to violence in extreme  
6. **Reciprocity** - One person functions lower because another overfunctions

Note: Person and Event are sibling entities with many-to-many relationships, not parent/child hierarchy.

### Four Key Variables (All Events track shifts in these over time)
- **Symptom**: Physical/mental health changes or challenges meeting goals
- **Anxiety**: Automatic response to real/imagined threat
- **Functioning**: Ability to balance emotion and intellect toward longer term goals (CORE INDEPENDENT VARIABLE)
- **Relationship**: Actions/behaviors toward others to decrease short-term discomfort

### Data Model Hierarchy
```
Person (id, name, spouses, offspring, parents, birthDate)
Event (id, description, dateTime, people[], variables)
├── Symptom (shift: up/down/same)
├── Anxiety (shift: up/down/same) 
├── Functioning (shift: up/down/same) - CORE CONSTRUCT
└── Relationship (kind + specific attributes)
    ├── Mechanisms (movers[], recipients[])
    │   ├── Distance, Conflict, Reciprocity, ChildFocus
    └── Triangle (inside_a[], inside_b[], outside[])
```

## Development Workflow Integration

### Domain-Specific AI Auditing Principles
- **Domain Alignment**: Prioritize Bowen Theory constructs over general AI metrics
- **Iterative Refinement**: Rapid feedback cycles with measurable improvements
- **Scalability**: Design for growth from 5-10 experts to broader user base
- **Traceability**: Link every feedback item to specific prompts/data points
- **Bias Mitigation**: Validate across diverse user inputs and scenarios

### When Adding Feedback Features
- Implement structured annotation interfaces with standardized forms
- Include both quantitative (ratings, boolean) and qualitative (comments, tags) feedback
- Design for expert efficiency while capturing nuanced domain insights
- Structure data for aggregation and fine-tuning dataset export

### When Updating Prompts
- Use iterative human-in-the-loop feedback cycles
- Continuous updates based on error pattern analysis
- Include expert-derived positive/negative examples from feedback
- Version control with correlation to feedback periods and improvement metrics
- A/B testing for comparing prompt strategies

### When Building Analytics
- Focus on domain-specific error categories (Functioning shifts, Triangle misidentification)
- Aggregate feedback to identify patterns without manual review bottlenecks
- Calculate precision/recall for extraction accuracy, ordinal ratings for conversational quality
- Export structured datasets for future fine-tuning preparation
- Track improvement trends pre/post prompt updates# CONTEXT.md

## Technical Architecture Strategy

### Auditing Workflow (Domain-Specific AI Best Practices)
**Phase 1: Expert-Driven Auditing**
- Experts act as both users (mobile app) and auditors (web interface)
- Focus on data extraction validation and conversational flow assessment
- Iterative human-in-the-loop feedback for rapid AI refinement

**Phase 2: Non-Expert Beta Testing**
- Non-experts use mobile app for realistic interactions
- Experts audit via web interface to validate generalization
- Identify edge cases and ensure broader audience compatibility

### Current Feedback Collection (Implemented)
- **Data Extraction Feedback**: Boolean accuracy (thumbs up/down), field-specific corrections, manual PDP construction
- **Conversational Flow Feedback**: 1-5 ratings, predefined tags, detailed notes
- **Database**: PostgreSQL with Feedback and ExpectedPDP tables for concurrency
- **Traceability**: Links to specific data_point_id/conversation_turn_id

### Enhanced Feedback Mechanisms
**Data Extraction Feedback**
- Boolean accuracy per data point (Person, Event, Relationship)
- Field-specific corrections via dropdowns/inputs
- Manual PDP construction with expected vs. actual comparison
- Notes field for detailed Bowen Theory context

**Conversational Flow Feedback**
- Ordinal ratings (bad, mediocre, good) for specific criteria
- Predefined tags: "too_abrupt", "lacks_empathy", "misses_family_context"
- Free-text comments for nuanced insights

### Scaling Workflow (To Implement)
1. **Structured Annotation**: Prebuilt forms for standardized corrections
2. **Error Categorization**: Extraction errors vs. conversational tone issues
3. **Iterative Refinement**: Continuous feedback cycles with prompt updates
4. **A/B Testing**: Compare different prompt strategies based on expert feedback
5. **Version Control**: Track AI behavior changes correlated with feedback

### Key Metrics to Track
- **Quantitative**: Precision/recall for data extraction, ordinal ratings for response quality
- **Qualitative**: Pattern analysis from free-text comments and tags
- **Error patterns**: Frequency of specific tags and correction types
- **Improvement trends**: Pre/post prompt update comparisons

### Implementation Priorities
1. **Error Analysis Dashboard** - Categorized error reporting
2. **Prompt Management** - Version control with feedback correlation
3. **Dataset Export** - Structured format for fine-tuning preparation

## Conversational Style Guidelines

### AI Coaching Role (Not Therapist)
- Consultant, not therapist - cannot diagnose or treat
- Focus on gathering information vs. emotional support
- Avoid "feeling words" - prefer objective/measurable language
- One question at a time, place events in time
- Help clarify problems and priorities

### Bowen Theory Coaching Process
1. **Clarify the problem** - Physical/mental symptom or life challenge
2. **Gather problem timeline** - When start/better/worse/disappear/reappear
3. **Identify notable periods** - Markedly better/worse progress points
4. **Collect context** - Life/relationship shifts around notable periods
5. **Map family system** - 3+ generations, relationships, triangles, mechanisms

## Error Prioritization Framework

### High Impact (Address First)
- Triangle misidentification - Central to Bowen Theory
- ChildFocus recipient errors - Should be single child
- Missing multigenerational context - 3+ generations required

### Medium Impact
- Mechanism mover/recipient misassignment
- Shift direction errors (up/down/same)
- Timeline/dating inaccuracies

### Low Impact (Address Last)
- Minor Person.name variations
- Confidence score calibration
- Description text refinements

## Auditing System Architecture

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

### Interface Design Strategy
**Mobile App**
- Chat interface for experts acting as users
- Simple feedback buttons (thumbs-up/down, ordinal ratings) per response
- Pop-up forms for detailed notes and corrections
- Responsive design for phone interaction

**Web Interface**
- **Data Model Tab**: Collapsible tables for Person, Event, Relationship with feedback forms per row
- **Conversation Tab**: Chat-like feed with rating dropdowns and tag checkboxes per response
- **Feedback Summary Tab**: Aggregated metrics filterable by expert/user
- **Manual PDP Entry**: Forms to input expected vs. actual data extractions
- Responsive design: Stacked layout (mobile) vs. side-by-side tables (desktop)

### Error Analysis Framework
**Extraction Errors**
- Wrong Person identification/roles
- Incorrect Event.kind assignment
- Misidentified relationship structures (Triangle vs. Mechanism)
- Variable shift direction errors (up/down/same)

**Conversational Errors**
- Lack of empathy/appropriate tone
- Missing Bowen Theory context probing
- Irrelevant or poorly timed questions
- Failure to elicit multigenerational information

### Auditing Techniques Implementation
1. **Structured Annotation**: Standardized forms with dropdowns for corrections
2. **Comparative Analysis**: A/B testing different prompt strategies
3. **Pattern Detection**: Automated clustering of similar feedback comments
4. **Iterative Refinement**: Weekly feedback cycles with measurable improvements
5. **Real vs. Simulated Testing**: Expert simulation followed by non-expert validation

## Success Metrics

### Short-term (Prompt Engineering)
- Increased accuracy rates for high-priority constructs
- Reduced manual review time per feedback cycle
- Expert satisfaction with prompt improvements

### Long-term (Fine-tuning Ready)
- Structured dataset of 100+ expert-validated conversations
- Clear improvement plateau indicating prompt engineering limits
- Resource availability for ML infrastructure

## Key Constraints

- **Domain Expertise Bottleneck**: Your PsyD + Bowen Theory knowledge is critical for prioritization
- **Expert Availability**: 5-10 domain experts for feedback, not full-time, not paid
- **Resource Limitations**: Solo developer, prefer automation over manual processes
- **Data Quality**: Expert validation required for fine-tuning dataset