# Bowen Theory Domain Spec

## Core Constructs (Priority Order for Errors)
1. **Functioning** - The independent variable; ability to balance emotion and intellect
2. **Triangle** - Two people align (inside) against a third (outside) to reduce discomfort
3. **ChildFocus** - Attention to real/perceived problem in a child (single child recipient)
4. **Distance** - Avoiding open communication up to cutoff in extreme
5. **Conflict** - Overt arguments up to violence in extreme
6. **Reciprocity** - One person functions lower because another overfunctions

Note: Person and Event are sibling entities with many-to-many relationships, not parent/child hierarchy.

## Four Key Variables (SARF)
All Events track shifts in these over time:
- **Symptom**: Physical/mental health changes or challenges meeting goals
- **Anxiety**: Automatic response to real/imagined threat
- **Functioning**: Ability to balance emotion and intellect toward longer term goals (CORE INDEPENDENT VARIABLE)
- **Relationship**: Actions/behaviors toward others to decrease short-term discomfort

## Data Model Hierarchy
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

## Domain Constraints

### Triangle Exclusivity
Triangles are exclusively Inside/Outside relationship types. Only Inside and Outside events use `relationshipTriangles`. Other relationship types (Fusion, Conflict, Distance, Reciprocity, ChildFocus) use `relationshipTargets` only — they do not have triangle members.

Inside/Outside triangle semantics in `_do_addItem`:
- mover→targets: event's relationship kind
- mover→triangles: always Outside
- targets→triangles: opposite of event's relationship kind

## AI Coaching Role (Not Therapist)
- Consultant, not therapist — cannot diagnose or treat
- Focus on gathering information vs. emotional support
- Avoid "feeling words" — prefer objective/measurable language
- One question at a time, place events in time
- Help clarify problems and priorities

## Coaching Process
1. **Clarify the problem** - Physical/mental symptom or life challenge
2. **Gather problem timeline** - When start/better/worse/disappear/reappear
3. **Identify notable periods** - Markedly better/worse progress points
4. **Collect context** - Life/relationship shifts around notable periods
5. **Map family system** - 3+ generations, relationships, triangles, mechanisms

## Error Prioritization

### High Impact (Address First)
- Triangle misidentification — Central to Bowen Theory
- ChildFocus recipient errors — Should be single child
- Missing multigenerational context — 3+ generations required

### Medium Impact
- Mechanism mover/recipient misassignment
- Shift direction errors (up/down/same)
- Timeline/dating inaccuracies

### Low Impact (Address Last)
- Minor Person.name variations
- Confidence score calibration
- Description text refinements
