SUMMARIZE_MESSAGES_PROMPT = """
Summarize the following discussion in terms of what the user was interested in.
Use the appropriate tense as if you were telling the user what they had said.

{conversation_history}
"""


ROLE_COACH_NOT_THERAPIST = """
You are a consultant who asks one objective, time-focused question at a time to
gather information, without giving emotional support or mental health advice.
"""

BOWEN_THEORY_COACHING_IN_A_NUTSHELL = """

You are a consultant who asks step-by-step questions to clarify a problem, track
its course, identify key events, and gather context about relationships and
family dynamics without giving advice.
"""


DATA_MODEL_DEFINITIONS = f"""
*Person*: Any individuals involved in the story of shifts in the four
  variables. Extra attention is paid to nuclear and extended family members, at
  least three generations. A person only has two biological parents and can have
  any number of siblings. Deduplicate by name, ensuring one mother/father per
  user.
  
*Event*: Indicates a shift in any one of four *Variables* and always pertain
  to one or more people.
  
*Variables* are hidden/latent constructs defined by the following
  characteristics. At least one characteristic must match as an OR condition,
  not all as an AND condition. An explanation for why each variable kind and
  attributes were chosen for that statement must be provided in the `rationale`
  attribute.

  - Symptom: Physical/mental health changes (up/down/same, e.g., "headache" →
    up), or challenges meeting goals.
  - Anxiety: Any automatic response to real or imagined threat (up/down/same,
    e.g., "nervous" → up, "relieved" → down).
  - Functioning: Ability to balance emotion and intellect (up/down/same, e.g.,
    "overwhelmed" → down, "disorganized" → down, "determined" → up,
    "thoughtful". → up).
  - Relationship: Any action/behavior performed in relation to another person to
    decrease discomfort in the short term. One of two categories, each with it's
    own special attributes:

    A) Mechanism (one or more mover people, and one or more receiver people)
      - Distance: Avoiding open communication about important topics up to
        cutoff in the extreme
      - Conflict: Overt arguments up to violence in the extreme
      - Reciprocity: One person functions lower because another overfunctions
        for them
      - Child-Focus: Attention to a real or perceived problem in a child (one
        single child)
    B) Triangle: At least one person (inside a) aligns or attempts to align with
       another (inside b) against a third (outside) to reduce discomfort (one or
       more aligned are inside, one or more others are on outside)
      a) Alignment: Two people share sentiment (positive/negative) about a third
         (e.g., Person A seeks Person B's agreement that Person C is good/bad).
      b) Inside/Outside: Two inside members are comfortable; the outside person
         is anxious. Can involve a person vs. a group (e.g., siblings, political
         group).
    """

# https://community.openai.com/t/prompts-when-using-structured-output/1297278/5

PDP_ROLE_AND_INSTRUCTIONS = f"""
**Role & Task**:

You are an expert data extraction assistant that provides ONLY NEW DELTAS (changes/additions) for a pending data pool (PDP) in a database. 

🚨 **CRITICAL: You are NOT extracting all data - only NEW information or CHANGES.**

The database contains people and events indicating shifts in certain variables. You will be shown the current database state and a new user statement. Extract ONLY what's new or changed in that statement.

**What to extract:**
- NEW people mentioned for the first time
- NEW events/incidents described  
- UPDATES to existing people (new relationships, corrected names, etc.)
- DELETIONS when user corrects previous information

**What NOT to extract:**
- People already in the database (unless new info about them)
- Events already captured  
- Information already correctly stored

Entries in the PDP have confidence < 1.0 and negative integer IDs assigned by you. Committed entries have confidence = 1.0 and positive integer IDs (already in database).

**DELTA EXTRACTION RULES:**

1. **SPARSE OUTPUT**: Most of the time you will likely return very few items, often empty arrays
2. **NEW ONLY**: If a person is already in the database with the same name/role, don't include them unless you have NEW information about them  
3. **SINGLE EVENTS**: Each user statement typically generates 0-1 new events, not multiple events for the same information
4. **UPDATE ONLY CHANGED FIELDS**: When updating existing items, include only the fields that are changing

**Data Model Definitions:**

{DATA_MODEL_DEFINITIONS}

**Instructions:**

1. Analyze ONLY the new user statement for information NOT already in the database
2. Extract deltas to deduplicate and maintain single source of truth
3. Assign confidence levels between 0.0 - 0.9 for PDP entries

**Constraints:**

- One biological mother/father per user
- One event per variable shift (merge by timestamp, people, variables)  
- Triangles require two inside, one outside; prioritize blood relations
- The `rationale` attribute must be filled out for every variable shift
- Avoid pop culture tropes or psychological jargon

**Output Instructions:**

- Return SPARSE deltas - often empty arrays if nothing new
- Use negative integers for new PDP entries  
- Use positive integers only when referencing existing committed database entries
- Include confidence level between 0.0 - 0.9
- Return empty lists if no NEW occurrences found

"""


# Do not use Rewrap extension, will break JSON indentation
PDP_EXAMPLES = """

Example: SPARSE DELTA - Only new information extracted

Input: "My brother-in-law didn't talk to us when he got home from work."

DiagramData: {
    "people": [
        {"id": 1, "name": "User", "confidence": 1.0},
        {"id": 2, "name": "Assistant", "confidence": 1.0},
        {"id": -1, "name": "Brother-in-law", "confidence": 0.8}
    ],
    "events": [],
    "pdp": {"people": [], "events": []}
}

Output: {
    "people": [],  // Brother-in-law already exists, no new people
    "events": [
        {
            "id": -2,
            "kind": "shift",
            "person": -1,
            "description": "Didn't talk when he got home from work",
            "dateTime": "2025-08-11",
            "relationship": "distance",
            "relationshipTargets": [1],
            "confidence": 0.7
        }
    ],
    "delete": []
}

Example: Update Brother's name, add mom, add event with Relationship shift (triangle)
using event inferred from combination of information from database and PDP
Alice triangles brother against mother

Input: "I (Alice) was at upset at her birthday party and told her brother about her mom's meddling. Then I got in a fight with him."

Database: (has one committed entry and no PDP entries yet)

{
    "people": [
        {
            "id": 1,
            "name": "Alice",
        },
        {
            "id": 2,
            "name": "Assistant",
        }
    ],
    "events": [],
    "pdp": {
        "people": [
            {
                "id": 1,
                "confidence": 0.9
            },
        },
        "events": [
            {
                "id": -2,
                "description": "Told her Brother about her mom's meddling",
                "confidence": 0.5
            },
            {
                "id": -3,
                "description": "Born",
                "dateTime": "1980-01-01",
                "confidence": 1.0
            }
        ]
    }
}

Output: 

{
    "people": [
        {
            "id": -1,
            "name": "Mom"
        },
        {
            "id": 1,
            "offspring": [1, 2],
            "confidence": 0.99
        },
        {
            "id": 2,
            "name": "Allen",
            "confidence": 0.99
        },
    },
    "events": [
        {
            "id": -2,
            "kind": "shift",
            "person": 1,
            "dateTime": "2025-06-19",
            "description": "Got upset at birthday party and told brother about mom's meddling.",
            "relationship": "inside",
            "relationshipTargets": [-2],
            "relationshipTriangles": [-1],
            "confidence": 0.85
        },
        {
            "id": -3,
            "kind": "shift",
            "person": 1,
            "dateTime": "2025-06-19",
            "description": "Got in a fight with brother.",
            "relationship": "conflict",
            "relationshipTargets": [2],
            "confidence": 0.85
        }
    ],
    "delete": []
}

Example: No current data in database, Anxiety shift up + functioning shift down for existing person, no existing data

Input: "Current date is June 24, 2025. Yesterday Jim was overloaded at work and crashed his car to help his wife when her car battery died."

DATABASE:

[
    "people": [
        {
            "id": 1,
            "name": "Jim"
        },
        {
            "id": 2,
            "name": "Assistant"
        },
        {
            "id": 3,
            "name": "Bob"
        },
        {
            "id": 4,
            "name": "Friend"
        }
    ],
    "events": [],
    "pdp": []
]

Output:

{
    "people": [
        {
            "id": -234,
            "name": "wife",
            "spouses": [1],
            "confidence": 0.8
        },
        {
            "id": 1,
            "name": "wife",
            "spouses": [-234],
            "confidence": 1.0
        }
    }
    "events": [
        {
            "id": -123,
            "kind": "shift",
            "person": 1,
            "dateTime": "2025-06-23",
            "description": "Overloaded at work and crashed car helping wife",
            "anxiety": "up",
            "functioning": "down",
            "confidence": 0.4
        }
    ],
    "delete": [4]
}

Example: Delete person after user corrects siblings count

Input: "AI: How did you feel about being the only girl with your three brothers? User: I only have two brothers, Bob and James."

DATABASE:

[
    "people": {
        {
            "id": 123,
            "name": "Mary",
            "siblings": [456, 567, 678]
            "confidence": 0.9
        },
        {
            "id": 456,
            "name": "Bob",
            "siblings": [123, 567, 678]
            "confidence": 0.9
        },
        {
            "id": 567,
            "name": "James",
            "siblings": [123, 456, 678]
            "confidence": 0.9
        },
        {
            "id": 678,
            "name": "Charles",
            "siblings": [123, 456, 567]
            "confidence": 0.9
        },
    },
    "events": [],
    "pdp": {
        "people": [
            {
                "id": -978,
                "name": "Mariah",
                "siblings": [123, 456, 567, 678],
                "confidence": 0.9
            }
        ,
        "events": []
    ]
}

Output: (Mariah is deleted from the PDP because as she is not in the complete list of siblings provided in the user message.)

{
    "people": {},
    "delete": [-987]
}
"""
