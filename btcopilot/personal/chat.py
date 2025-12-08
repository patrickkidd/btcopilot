import textwrap
import logging

from dataclasses import dataclass
from flask import g

from btcopilot.extensions import db, ai_log, llm, LLMFunction
from btcopilot.async_utils import one_result
from btcopilot import pdp
from btcopilot.personal.models import Discussion, Statement
from btcopilot.schema import DiagramData, PDP, asdict
from btcopilot.personal.prompts import (
    ROLE_COACH_NOT_THERAPIST,
    BOWEN_THEORY_COACHING_IN_A_NUTSHELL,
    DATA_MODEL_DEFINITIONS,
)


_log = logging.getLogger(__name__)


@dataclass
class Response:
    statement: str
    pdp: PDP | None = None


def ask(discussion: Discussion, user_statement: str) -> Response:

    ai_log.info(f"User statement: {user_statement}")
    if discussion.diagram:
        diagram_data = discussion.diagram.get_diagram_data()
    else:
        diagram_data = DiagramData()

    new_pdp, pdp_deltas = one_result(
        pdp.update(discussion, diagram_data, user_statement)
    )

    # Write to disk
    diagram_data.pdp = new_pdp
    if discussion.diagram:
        discussion.diagram.set_diagram_data(diagram_data)

    statement = Statement(
        discussion_id=discussion.id,
        text=user_statement,
        speaker=discussion.chat_user_speaker,
        order=discussion.next_order(),
        pdp_deltas=asdict(pdp_deltas) if pdp_deltas else None,
    )
    db.session.add(statement)

    # Get the llm to generate a human-like response according to the direction
    # of the conversation and the context. Otherwise we would just have the same
    # canned response for each mode

    # Check for custom prompts in g context (used for testing)
    role_prompt = ROLE_COACH_NOT_THERAPIST
    bowen_prompt = BOWEN_THEORY_COACHING_IN_A_NUTSHELL
    data_model_prompt = DATA_MODEL_DEFINITIONS

    if hasattr(g, "custom_prompts"):
        role_prompt = g.custom_prompts.get("ROLE_COACH_NOT_THERAPIST", role_prompt)
        bowen_prompt = g.custom_prompts.get(
            "BOWEN_THEORY_COACHING_IN_A_NUTSHELL", bowen_prompt
        )
        data_model_prompt = g.custom_prompts.get(
            "DATA_MODEL_DEFINITIONS", data_model_prompt
        )

    meta_prompt = textwrap.dedent(
        f"""
        {role_prompt}

        **Data Model Definitions**

        {data_model_prompt}

        **Instructions**

        Your goal is to first thoroughly understand the presenting problem, then
        pivot to systematically collecting family structure data for a
        three-generation diagram.

        {bowen_prompt}

        **Where are you in data collection?** Review the conversation history:

        **Phase 1 - Presenting Problem (do this FIRST, 5-10 exchanges):**
        - [ ] What exactly is the problem?
        - [ ] When did it start?
        - [ ] Who is involved?
        - [ ] How does each person feel about it? (ask, move on if no engagement)
        - [ ] Has it gotten better or worse?
        - [ ] What are the biggest challenges/uncertainties?
        - [ ] What prompted seeking help now?

        Have you fully understood the presenting problem? If not, keep asking
        about it. If yes, pivot to family data.

        **Phase 2 - Family of Origin (after problem is understood):**
        - [ ] Mother: name?
        - [ ] Mother: age (or death year/cause)?
        - [ ] Father: name?
        - [ ] Father: age (or death year/cause)?
        - [ ] Parents together or divorced? When?
        - [ ] Siblings: names and ages?

        **Phase 3 - Extended Family:**
        - [ ] Maternal grandmother: name? alive/deceased?
        - [ ] Maternal grandfather: name? alive/deceased?
        - [ ] Paternal grandmother: name? alive/deceased?
        - [ ] Paternal grandfather: name? alive/deceased?
        - [ ] How many aunts/uncles on each side?

        **Phase 4 - User's Own Family (if married/partnered):**
        - [ ] Spouse name and age?
        - [ ] When married?
        - [ ] Children: names and ages?

        **Phase 5 - Timeline of Nodal Events (help them tell the family's story):**

        Nodal events often correlate with symptoms in ways people don't see until
        asked. Guide them through the family timeline with warm, specific questions:

        - [ ] "Has anyone in the family died in the last few years? What was that
              like for everyone?"
        - [ ] "Any serious illnesses or health scares? When did those happen?"
        - [ ] "Any marriages or divorces - in your generation or your parents'?"
        - [ ] "Has anyone made a big move? Across country, or in/out of a household?"
        - [ ] "Any job changes, retirements, financial setbacks?"
        - [ ] "Is anyone in the family not speaking to each other?"

        **The Critical Connection** - gather symptom facts FIRST, then connect:
        - [ ] "When did your symptoms start?" (get the date/timeframe first)
        - [ ] "Did they come on suddenly or gradually?"
        - [ ] "Have they gotten better or worse over time?"
        - [ ] THEN ask: "What was going on in the family around that time?"
        - [ ] "Looking back, do you see any connection between these family events
              and how you were feeling?"

        **Your next response (2-3 sentences):**
        1. Optional: Very brief acknowledgment (a word or two, not restating what they said)
        2. Ask for the next missing data point from the current phase
        3. If pivoting from problem to family: "OK, I have a good picture of
           what's going on. Now let me get some family background. What's your
           mom's name and how old is she?"

        **Do NOT parrot back what the user just said.** Move the conversation forward.

        **NEVER use these phrases**:
        - "It sounds like..." / "That sounds..."
        - "It makes sense that you're feeling..."
        - "That must be hard/frustrating/difficult"
        - "How does that make you feel?" (unless gathering emotional facts
          about the presenting problem)
        - "Tell me more" (too vague - ask for specific facts)

        **Response style**:
        - Direct factual questions - be SPECIFIC, not vague
        - BAD: "Are there any significant family events?" (too vague)
        - GOOD: "Has anyone in the family died in the last few years?"
        - GOOD: "Any serious illnesses or accidents recently?"
        - When they give info, acknowledge briefly then ask next question
        - Don't give advice or try to solve the problem - just gather facts

        **Conversation History**

        {discussion.conversation_history()}

        **Last User Statement**

        {user_statement}
        """
    )

    ai_response = _generate_response(discussion, diagram_data, meta_prompt)
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
    discussion: Discussion, diagram_data: DiagramData, meta_prompt: str
) -> str:
    ai_response = llm.submit_one(LLMFunction.Respond, meta_prompt, temperature=0.45)
    return ai_response.strip()
