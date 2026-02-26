"""
Synthetic conversation testing for conversational quality evaluation.

Components:
1. Persona - LLM-based user personas with behavioral traits
2. ConversationSimulator - Alternates between chatbot and simulated users
3. QualityEvaluator - Automated checks for robotic patterns
"""

import json
import re
import enum
import logging
import pickle
from dataclasses import dataclass, field

from btcopilot.extensions import db
from btcopilot.llmutil import gemini_text_sync
from btcopilot.personal.models import Discussion, DiscussionStatus, Speaker, SpeakerType
from btcopilot.pro.models import Diagram, User
from btcopilot.schema import DiagramData, asdict


_log = logging.getLogger(__name__)


class PersonaTrait(enum.StrEnum):
    Evasive = "evasive"
    Oversharing = "oversharing"
    ConfusedDates = "confused_dates"
    Defensive = "defensive"
    Tangential = "tangential"
    Terse = "terse"
    Emotional = "emotional"
    Mature = "mature"
    HighFunctioning = "high_functioning"


class AttachmentStyle(enum.StrEnum):
    Secure = "secure"
    AnxiousPreoccupied = "anxious_preoccupied"
    DismissiveAvoidant = "dismissive_avoidant"
    FearfulAvoidant = "fearful_avoidant"


class DataCategory(enum.StrEnum):
    PresentingProblem = "presenting_problem"
    Mother = "mother"
    Father = "father"
    ParentsStatus = "parents_status"  # married, divorced, remarried
    Siblings = "siblings"
    MaternalGrandparents = "maternal_grandparents"
    PaternalGrandparents = "paternal_grandparents"
    AuntsUncles = "aunts_uncles"
    Spouse = "spouse"
    Children = "children"
    NodalEvents = "nodal_events"  # deaths, illnesses, marriages, divorces, moves


@dataclass
class DataPoint:
    category: DataCategory
    keywords: list[str]  # keywords that indicate AI asked about this


# --- Prompt Constants ---
# Condensed from doc/specs/SYNTHETIC_CLIENT_PROMPT_SPEC.md
# Budget: ~2050 chars total instructions (backgrounds can be up to 5.5K within 8K limit)

_ANTI_PATTERNS = (
    "Don't deliver backstory in organized paragraphs — details come out across multiple turns.\n"
    "Don't use therapy-speak ('my anxiety stems from', 'I realize I have a pattern of', 'I've been processing').\n"
    "Don't answer emotional questions with self-aware analysis — describe experiences, not diagnoses. "
    "You do NOT have clinical insight into your own defense mechanisms. You don't know why you do what you do — "
    "you just do it. If you notice a pattern, express confusion about it, not understanding.\n"
    "Don't volunteer the exact info the coach is looking for — make them work for it.\n"
    "Don't present emotions as a list. Pick one: 'Mostly I was just mad.'\n"
    "Don't start responses with the same filler words every time.\n"
    "Don't end responses with rhetorical questions more than once or twice in the whole conversation. "
    "Real people don't punctuate every answer with 'Why does that matter?' or 'Does that make sense?' — "
    "they just stop talking.\n"
    "Don't repeat the same verbal tic across multiple turns ('Anyway, it's fine', 'I don't know', etc). "
    "Vary how you close out a thought."
)

_CONVERSATIONAL_REALISM = (
    "Early on, you may ask what the coach needs: 'How does this work?' or express surprise: 'My grandparents? Why?'\n"
    "Correct yourself mid-thought. Trail off on hard topics. Lose the thread: 'Sorry, what were you asking?'\n"
    "Circle back to earlier topics. Use hedging: 'I think,' 'probably,' 'as far as I know.'\n"
    "Sometimes answer what's on your mind rather than what was asked."
)

_RESPONSE_LENGTH = (
    "Factual questions = short: 'She's 68.' 'Two brothers.'\n"
    "Emotional territory = longer, messier — rambling, trailing off, but still conversational.\n"
    "Caught off guard = short: 'I don't know' / 'That's complicated.'\n"
    "Vary your length turn to turn. A long vulnerable answer should be followed by something shorter — "
    "you said a lot and need the coach to respond. Two long answers in a row feels like a monologue, not a conversation.\n"
    "When you have more to say than fits naturally, stop and let the coach pull it out of you."
)

_MEMORY_RULES = (
    "Core facts stay consistent (names, dates, who's alive) but your interpretation may shift as you talk.\n"
    "Some memories are vivid with sensory details. Some are vague: 'The years blur together.' Some are blank.\n"
    "If two things don't add up, try to reconcile mid-conversation.\n"
    "Other people's versions compete with yours."
)

_TRAIT_BEHAVIORS = {
    PersonaTrait.Evasive: (
        "Answer a different question than asked. Give the short version, wait to be asked more.\n"
        "Redirect: 'Can we come back to that?' Go vague: 'It was a while ago.'\n"
        "Use others as shields: 'You'd have to ask my sister.'\n"
        "Minimize: 'It was fine.' Answer literally — logistics, not feelings."
    ),
    PersonaTrait.Oversharing: (
        "Jump ahead before the coach gets there. Provide unsolicited context in nested digressions.\n"
        "Connect dots out loud: 'I think it's all connected.' Give more emotional detail than asked.\n"
        "Offer informal theories. Have trouble stopping: 'Sorry, I'm rambling' then keep going."
    ),
    PersonaTrait.ConfusedDates: (
        "Round to approximate periods: 'A few years ago.' Anchor to life events: 'right after Jake was born.'\n"
        "Be confidently wrong sometimes. Mix up similar events. Hedge: 'Maybe 2018? Or 2019.'\n"
        "Sequence events wrong. Defer: 'My husband would know the exact date.'"
    ),
    PersonaTrait.Defensive: (
        "Push back: 'Why does that matter?' Reframe: 'I didn't abandon — I needed space.'\n"
        "Get offended by neutral questions. Pre-empt: 'I know this sounds bad, but...'\n"
        "Shut down questions: 'I don't want to get into that.'\n"
        "Use anger to cover vulnerability — get sharper right before admitting something."
    ),
    PersonaTrait.Tangential: (
        "Start answering but get pulled into side stories through personal associations.\n"
        "Don't self-correct — keep going until the coach redirects.\n"
        "Come back from unexpected angles. Tell stories within stories.\n"
        "More emotional = more tangents."
    ),
    PersonaTrait.Terse: (
        "Answer in fragments: 'Fine.' 'Yeah.' 'Two brothers.'\n"
        "Require follow-ups for detail. Use silence as a response.\n"
        "Give more when the topic matters. Resist elaboration: 'That's basically it.'\n"
        "Emotion through clipped language: 'It sucked.'"
    ),
    PersonaTrait.Emotional: (
        "Shift tone mid-sentence — start calm and escalate.\n"
        "Circle back to the most painful part. Apologize: 'Sorry, I didn't think I'd get upset.'\n"
        "React with emotion before facts. Get overwhelmed: 'Can we talk about something else?'\n"
        "Show emotion through specific details, not labels."
    ),
}

_HIGH_FUNCTIONING_BEHAVIORS = (
    "Give organized answers but not comprehensive ones — let the coach follow up.\n"
    "Show genuine curiosity: 'Is it common for this to skip a generation?'\n"
    "Offer reflections as genuine questions, not rehearsed insights.\n"
    "Have appropriate emotional responses. Know your limits: 'I don't know what I felt about it.'"
)
_TRAIT_BEHAVIORS[PersonaTrait.Mature] = _HIGH_FUNCTIONING_BEHAVIORS
_TRAIT_BEHAVIORS[PersonaTrait.HighFunctioning] = _HIGH_FUNCTIONING_BEHAVIORS

_ATTACHMENT_NARRATIVE = {
    AttachmentStyle.Secure: (
        "Your narrative is coherent — you describe both positive and negative experiences "
        "with appropriate emotional range and comfort with not knowing."
    ),
    AttachmentStyle.AnxiousPreoccupied: (
        "Your narrative floods with detail, seeks reassurance, and returns to the same worries — "
        "you're preoccupied with how others perceive you."
    ),
    AttachmentStyle.DismissiveAvoidant: (
        "Your narrative sounds complete but lacks emotional content — "
        "you give facts and logistics while minimizing the importance of relationships."
    ),
    AttachmentStyle.FearfulAvoidant: (
        "Your narrative is fragmented and contradictory — you start to disclose then abruptly "
        "shut down, shifting between wanting connection and fearing it."
    ),
}


@dataclass
class Persona:
    name: str
    background: str
    attachmentStyle: AttachmentStyle
    traits: list[PersonaTrait] = field(default_factory=list)
    presenting_problem: str = ""
    dataPoints: list[DataPoint] = field(default_factory=list)

    def system_prompt(self) -> str:
        # Deduplicate shared trait behavior text (Mature/HighFunctioning share)
        seen = set()
        trait_lines = []
        for t in self.traits:
            if t in _TRAIT_BEHAVIORS:
                text = _TRAIT_BEHAVIORS[t]
                if id(text) not in seen:
                    seen.add(id(text))
                    trait_lines.append(text)

        parts = [
            f"You are {self.name}, a person seeking help with a family issue.\n",
            f"**Background:**\n{self.background}\n",
            f"**Presenting Problem:**\n{self.presenting_problem}\n",
            f"**Anti-Patterns (CRITICAL):**\n{_ANTI_PATTERNS}\n",
            f"**Conversational Realism:**\n{_CONVERSATIONAL_REALISM}\n",
            f"**Response Length:**\n{_RESPONSE_LENGTH}\n",
            f"**Memory:**\n{_MEMORY_RULES}\n",
        ]
        if trait_lines:
            parts.append(
                "**Your Behavioral Traits:**\n" + "\n\n".join(trait_lines) + "\n"
            )
        parts.append(
            f"**Narrative Style:**\n{_ATTACHMENT_NARRATIVE[self.attachmentStyle]}\n"
        )
        parts.append(f"Respond only as {self.name}. Do not include meta-commentary.")

        return "\n".join(parts)


# Frozen personas preserved as reference examples for the generation prompt.
# Sarah, Marcus, Jennifer are already coded as ground truth — backgrounds unchanged.
DEPRECATED_PERSONAS = [
    Persona(
        name="Sarah",
        background="""42-year-old woman, works as a teacher.

**Own Family:**
- Married to David (44) for 14 years
- Two kids: Emma (12) and Jake (8)

**Parents:**
- Mother: Carol (68), diagnosed with early-stage dementia 6 months ago, lives alone
- Father: Richard (70), lives in Florida with girlfriend
- Parents divorced when Sarah was 15 (1997)
- Mother remarried briefly to Stan but divorced him in 2005
- Father never remarried

**Siblings:**
- Younger brother: Michael (38), lives in same city, married with 1 kid

**Grandparents:**
- Maternal grandmother: Ruth, died 2018 (stroke)
- Maternal grandfather: Harold, died 2010 (heart attack)
- Paternal grandmother: Margaret (92), in nursing home
- Paternal grandfather: George, died 1995 (cancer)

**Aunts/Uncles:**
- Mom has one sister, Aunt Linda (65)
- Dad has two brothers, Uncle Tom and Uncle Bill

**Nodal Events with Emotional Process:**

*Parents' divorce (1997) - Sarah was 15:*
- Sarah's anxiety went through the roof during this period - couldn't focus at school, grades dropped
- She stopped eating much, lost weight, her pediatrician was concerned
- Mom leaned heavily on Sarah for emotional support - they'd talk for hours about Dad
- Sarah distanced from her father - barely spoke to him for two years after he left
- Triangle: Sarah aligned with Mom against Dad; brother Michael stayed neutral and Sarah resented him for it
- Sarah felt responsible for "holding Mom together" during this time

*Grandmother Ruth's death (2018):*
- Sarah was very close to Ruth - talked to her weekly, visited monthly
- After Ruth died, Sarah had her first real episode of insomnia - lasted about 3 months
- She got irritable with David and the kids during this period
- Mom fell apart after Ruth died - Sarah had to manage the funeral because Mom couldn't function
- Sarah's functioning at work declined - took more sick days, felt overwhelmed
- Triangle: Sarah and Aunt Linda got into conflict over Ruth's belongings; Mom sided with Linda

*Mom's dementia diagnosis (6 months ago):*
- Sleep problems returned immediately - wakes at 3am worrying
- Anxiety is constant now - racing thoughts, can't relax
- Having more arguments with David about how much time she spends at Mom's
- Brother Michael "doesn't do his share" - Sarah visits Mom 3x/week, Michael maybe once a month
- Sarah snapped at Emma recently for not helping around the house - felt guilty after
- Triangle: Sarah complains to David about Michael not helping; David says she takes on too much

**Relationship Patterns Sarah is aware of but won't volunteer unless asked:**
- She knows she tends to over-function when stressed (takes on too much, doesn't ask for help)
- She's aware she distances from David when anxious rather than talking to him
- She suspects her worry about Mom mirrors how Mom worried about Grandma Ruth
- She feels guilty that she's closer to Mom than to Dad and wonders if that's fair""",
        attachmentStyle=AttachmentStyle.DismissiveAvoidant,
        traits=[PersonaTrait.Evasive, PersonaTrait.Defensive],
        presenting_problem="I haven't been sleeping well. My doctor said it might be stress but I don't know.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["sleep", "anxious", "anxiety", "dementia"],
            ),
            DataPoint(DataCategory.Mother, ["carol", "mother", "mom"]),
            DataPoint(DataCategory.Father, ["richard", "father", "dad"]),
            DataPoint(
                DataCategory.ParentsStatus, ["divorce", "divorced", "remarried", "stan"]
            ),
            DataPoint(DataCategory.Siblings, ["michael", "brother"]),
            DataPoint(
                DataCategory.MaternalGrandparents,
                ["ruth", "harold", "grandmother", "grandfather"],
            ),
            DataPoint(DataCategory.PaternalGrandparents, ["margaret", "george"]),
            DataPoint(
                DataCategory.AuntsUncles, ["aunt", "uncle", "linda", "tom", "bill"]
            ),
            DataPoint(DataCategory.Spouse, ["david", "husband", "married"]),
            DataPoint(DataCategory.Children, ["emma", "jake", "kids", "children"]),
            DataPoint(
                DataCategory.NodalEvents, ["1997", "2018", "2010", "died", "death"]
            ),
        ],
    ),
    Persona(
        name="Marcus",
        background="""28-year-old man, software engineer, lives alone in apartment.

**Own Family:**
- Single, recently broke up with girlfriend Jennifer (26) after 2 years
- No children

**Parents:**
- Mother: Patricia (58), works as nurse, lives in suburbs
- Father: Robert (60), retired teacher
- Parents still married, 35 years

**Siblings:**
- Older sister: Amanda (32), lives in Seattle, married to Kevin, has daughter Lily (3)

**Grandparents:**
- Maternal grandmother: Helen, died 2022 (Alzheimer's)
- Maternal grandfather: Frank, died 2021 (pneumonia) - deaths were 8 months apart
- Paternal grandmother: Dorothy (84), lives independently
- Paternal grandfather: William, died 2015 (stroke)

**Aunts/Uncles:**
- Mom has two sisters (Aunt Beth, Aunt Carol) and one brother (Uncle Jim)
- Dad is an only child

**Nodal Events with Emotional Process:**

*Sister Amanda moved to Seattle (2019):*
- Family dinner blowup when Amanda announced the move - Mom cried, Dad got quiet and left the table
- Marcus felt caught in the middle - Amanda called him to vent about Mom being "controlling"
- Mom called Marcus multiple times that week upset about Amanda "abandoning" the family
- Triangle: Marcus aligned with Amanda against Mom's reaction, but felt guilty about it
- After Amanda left, Mom started calling Marcus more often - he felt pressure to fill the gap
- Marcus's work focus improved ironically - he threw himself into a big project to avoid family drama

*Grandfather Frank's death (October 2021):*
- Frank had been healthy, then got pneumonia and died within two weeks - shock to everyone
- Mom fell apart - took leave from work, couldn't stop crying for weeks
- Marcus drove out to parents' house every weekend for two months to "be there" for Mom
- Dad seemed fine on surface but was drinking more - Marcus noticed but didn't say anything
- Marcus felt anxious during this period - trouble concentrating at work, started having headaches
- He and Jennifer had their first big fight - she felt neglected, he felt she didn't understand

*Grandmother Helen's decline and death (2021-2022):*
- Helen was diagnosed with Alzheimer's in 2019, but decline accelerated after Frank died
- Mom became primary caregiver while still grieving Frank - exhausted, snapping at everyone
- Marcus felt helpless watching his mom deteriorate along with his grandmother
- Triangle: Mom complained to Marcus about her sisters not helping enough with Helen
- Marcus started having trouble sleeping - would lie awake thinking about his grandmother
- When Helen died (June 2022), Marcus felt relief mixed with guilt about feeling relieved
- Mom seemed almost calm after Helen died - "She's finally at peace with Dad"

*Breakup with Jennifer (3 months ago):*
- Jennifer wanted to get engaged after 2 years together - Marcus kept deflecting the conversation
- When she finally gave him an ultimatum, he panicked and said he "wasn't ready"
- She broke up with him - Marcus was surprised by how much it hurt
- His anxiety spiked - not sleeping well, lost 10 pounds, struggling to focus at work
- He's been isolating since - declining social invitations, spending more time alone
- Mom keeps asking if he's okay, which makes him more anxious

**Patterns Marcus will share freely (oversharing trait):**
- He knows he runs away from commitment - did same thing with previous girlfriend
- He sees that his family is "enmeshed" - Mom is too involved in everyone's lives
- He wonders if his fear of commitment is related to watching his grandparents' health decline

**Patterns Marcus won't connect unless asked:**
- His commitment fears intensified around the time his grandparents died
- He took on a caretaking role for Mom similar to how Amanda used to
- His physical symptoms (headaches, sleep, weight loss) correlate with family stress periods""",
        attachmentStyle=AttachmentStyle.AnxiousPreoccupied,
        traits=[PersonaTrait.Oversharing, PersonaTrait.Tangential],
        presenting_problem="So I just went through a breakup — well, she broke up with me technically — and I've been kind of a mess. Jennifer, we were together two years, and she wanted to get engaged but I just... I don't know. My sister says I have commitment issues, which, okay, maybe, but it's more complicated than that. Sorry, I'm already rambling.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["stuck", "commit", "relationship", "breakup"],
            ),
            DataPoint(DataCategory.Mother, ["patricia", "mother", "mom", "nurse"]),
            DataPoint(DataCategory.Father, ["robert", "father", "dad", "teacher"]),
            DataPoint(DataCategory.ParentsStatus, ["married", "parents"]),
            DataPoint(DataCategory.Siblings, ["amanda", "sister", "seattle"]),
            DataPoint(
                DataCategory.MaternalGrandparents, ["helen", "frank", "alzheimer"]
            ),
            DataPoint(DataCategory.PaternalGrandparents, ["dorothy", "william"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "uncle"]),
            DataPoint(DataCategory.Spouse, ["jennifer", "girlfriend"]),
            DataPoint(DataCategory.Children, []),
            DataPoint(
                DataCategory.NodalEvents, ["2021", "2022", "2019", "died", "moved"]
            ),
        ],
    ),
    Persona(
        name="Jennifer",
        background="""44-year-old woman, works as pediatrician in private practice.

**Own Family:**
- Married to Michael (45) for 16 years, high school sweethearts who reconnected at college
- Three children: Ethan (14), Olivia (11), and Ben (8)

**Parents:**
- Mother: Barbara (72), retired teacher, very involved grandmother - visits weekly
- Father: Richard (74), retired accountant
- Parents married 48 years, healthy relationship

**Siblings:**
- Older brother: Steven (47), lives nearby, married to Lisa (45, nurse), two kids (twins, 12)
- Younger brother: Kevin (40), single, lives in California, works in tech - family "worries" about him

**Grandparents:**
- Maternal grandmother: Ruth (96), in assisted living, remarkably sharp mind
- Maternal grandfather: Harold, died 2008 (stroke)
- Paternal grandmother: Dorothy, died 2015 (cancer)
- Paternal grandfather: George, died 2001 (heart attack - sudden)

**Aunts/Uncles:**
- Mom has two sisters: Aunt Carol (70), Aunt Mary (68) - close-knit, talk weekly
- Dad had one brother (Uncle Frank) who died in 2018 (heart attack)

**Michael's family (in-laws):**
- Mother-in-law: Helen (73), diagnosed with Parkinson's 1 year ago
- Father-in-law: Tom (75), healthy, retired banker
- Michael is an only child

**Nodal Events with Emotional Process:**

*Grandfather George's sudden death (2001) - Jennifer was 21:*
- George had a heart attack at 67 - no warning, collapsed at a family dinner
- Jennifer was in medical school - this event influenced her to become a doctor
- Dad was devastated - George was his hero, they'd worked together in the same firm
- Jennifer saw Dad cry for the first time - it affected her deeply
- Triangle: Jennifer became Dad's confidante during this time; brothers seemed less available
- She took on a caretaker role - checking on Dad, calling home more often

*Grandfather Harold's death (2008):*
- Harold had a stroke, lingered for three weeks, family gathered
- Ruth (his wife) was stoic - handled it with grace that Jennifer admired
- Mom was sad but functional - Jennifer noticed the contrast with how Dad handled George's death
- Jennifer was pregnant with Ethan during this time - the juxtaposition of death and new life
- She wondered what kind of parent she'd be - thought a lot about what she learned from her grandparents

*Grandmother Dorothy's death (2015):*
- Dorothy had cancer - a two-year decline with increasing care needs
- Jennifer helped coordinate care from a medical perspective - Dad leaned on her expertise
- This was when Jennifer noticed the family pattern of her being "the capable one"
- Her brother Kevin didn't come home until the very end - family resentment built
- Triangle: Mom complained to Jennifer about Kevin; Jennifer defended Kevin to Mom

*Uncle Frank's death (2018):*
- Dad's only brother died suddenly of a heart attack at 70
- Dad became withdrawn for months - Jennifer worried about depression
- She noticed Dad became more aware of his own mortality - started talking about wills, legacy
- Triangle: Jennifer coordinated between Mom and her aunts to support Dad
- Her brothers didn't step up much - Steven was "busy with work," Kevin "couldn't get away"
- Jennifer felt the familiar weight of being the responsible one

*Practice expanded (2022):*
- Jennifer took on two new partners and administrative responsibilities
- Her work hours increased significantly - less time with kids
- Michael picked up more parenting duties - he's very capable but Jennifer feels guilty
- She started missing some of Ben's soccer games - this bothers her more than she admits
- Triangle: Michael reassures Jennifer she's doing great; she doesn't fully believe him

*Mother-in-law Helen's Parkinson's diagnosis (1 year ago):*
- Michael was shaken - Helen was always so vibrant and independent
- Jennifer slipped into medical consultant mode - researched treatments, specialists
- She noticed she was more comfortable with the medical aspects than the emotional ones
- Michael leans on Jennifer for guidance but also seems to resent it sometimes
- Helen is struggling with the diagnosis - doesn't want to be a burden
- Jennifer visits more than Michael does - wonders if she's overcompensating

*Ethan entering adolescence (this year):*
- Ethan was always "her boy" - close, affectionate, loved spending time together
- Started pulling away around 13 - shorter answers, closed door, less eye contact
- Jennifer intellectually knows this is normal - emotionally it feels like rejection
- She finds herself hovering more, which pushes him away more
- Michael says "give him space" but that feels wrong to Jennifer
- She noticed she watches how Barbara (her mom) interacts with Steven's boys - looking for clues
- Triangle: Jennifer talks to Barbara about Ethan; Barbara says "boys just need space"

**What Jennifer will share readily (high-functioning, analytical):**
- Detailed family history with accurate dates
- Can articulate the presenting problem clearly
- Makes thoughtful connections between events and emotions
- Curious about patterns, asks follow-up questions

**Patterns Jennifer intellectualizes but doesn't feel:**
- Her caretaker role began with Grandfather George's death
- She always positioned herself as "the capable one" in her family
- She may be recreating with Ethan the closeness she had with her Dad
- Her professional competence becomes a shield against emotional vulnerability
- She's better at taking care of others than letting others take care of her""",
        attachmentStyle=AttachmentStyle.Secure,
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
        presenting_problem="My oldest is 14 and starting to pull away. I know it's developmentally normal but it's getting to me more than I expected.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["son", "pulling away", "adolescence", "patterns"],
            ),
            DataPoint(DataCategory.Mother, ["barbara", "mother", "mom", "teacher"]),
            DataPoint(DataCategory.Father, ["richard", "father", "dad", "accountant"]),
            DataPoint(DataCategory.ParentsStatus, ["married", "healthy"]),
            DataPoint(DataCategory.Siblings, ["steven", "kevin", "brother", "lisa"]),
            DataPoint(DataCategory.MaternalGrandparents, ["ruth", "harold"]),
            DataPoint(DataCategory.PaternalGrandparents, ["dorothy", "george"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "uncle"]),
            DataPoint(DataCategory.Spouse, ["michael", "husband"]),
            DataPoint(
                DataCategory.Children, ["ethan", "olivia", "ben", "kids", "children"]
            ),
            DataPoint(
                DataCategory.NodalEvents,
                ["2018", "2015", "2008", "died", "parkinson", "high school"],
            ),
        ],
    ),
]

# Empty — the web form is the sole path for new personas
PERSONAS = []


@dataclass
class Turn:
    speaker: str  # 'user' or 'ai'
    text: str


@dataclass
class ConversationResult:
    turns: list[Turn]
    persona: Persona
    quality: "QualityResult | None" = None
    coverage: "CoverageResult | None" = None
    discussionId: int | None = None


# --- Emotional Arc ---

_EMOTIONAL_ARC = {
    "early": (
        "You are in the early phase. You're still testing the waters — "
        "be more guarded than open. Keep answers shorter and more surface-level."
    ),
    "middle": (
        "You are opening up. You're starting to share things you didn't plan to say. "
        "Answers get longer on emotional topics, but not every question lands — some you "
        "brush past ('Yeah, I guess'), some you redirect from, some you actually dig into."
    ),
    "deep": (
        "You are in deep territory. You may hit a wall on something painful or have "
        "a breakthrough. Emotional responses are less controlled. But vulnerability isn't "
        "steady — after saying something raw, you might go quiet, deflect, or backpedal "
        "('I don't know why I said that' / 'Anyway it's fine'). The deeper you go, the "
        "more the conversation oscillates between openness and retreat."
    ),
}

_ARC_MODIFIERS = {
    PersonaTrait.Defensive: "Your defensive side means the arc is slower — you may not fully open up until much later.",
    PersonaTrait.Oversharing: "Your oversharing means you give too much too fast early on.",
    PersonaTrait.Evasive: "You open up on the presenting problem but stay closed on other topics.",
    PersonaTrait.Emotional: "Your emotional arc is volatile — swings between deeply engaged and pulling back.",
}


# Word-count targets by response mode. The model gets an explicit target in the prompt
# so it can self-regulate, plus a generous token ceiling to prevent runaway responses.
_RESPONSE_MODES = {
    "short": {"words": (15, 40), "ceiling": 120},
    "medium": {"words": (60, 120), "ceiling": 250},
    "long": {"words": (130, 220), "ceiling": 400},
}
_MODE_WEIGHTS = {
    "early": {"short": 0.40, "medium": 0.50, "long": 0.10},
    "middle": {"short": 0.20, "medium": 0.40, "long": 0.40},
    "deep": {"short": 0.30, "medium": 0.30, "long": 0.40},
}

_SENTENCE_ENDINGS = re.compile(r'[.!?…]["\')\]]*\s')


def _trim_to_sentence(text: str) -> str:
    if not text:
        return text
    if text[-1] in ".!?…" or text.endswith('..."') or text.endswith("...'"):
        return text
    matches = list(_SENTENCE_ENDINGS.finditer(text))
    if matches:
        return text[: matches[-1].end()].strip()
    return text


def simulate_user_response(
    persona: Persona, history: list[Turn], turn_num: int = 0, max_turns: int = 20
) -> str:
    import random

    history_text = "\n".join(
        f"{'Coach' if t.speaker == 'ai' else 'You'}: {t.text}" for t in history
    )

    # Determine emotional arc phase
    if turn_num <= 5:
        phase_key = "early"
    elif turn_num <= 15:
        phase_key = "middle"
    else:
        phase_key = "deep"

    arc_phase = _EMOTIONAL_ARC[phase_key]
    arc_modifiers = [_ARC_MODIFIERS[t] for t in persona.traits if t in _ARC_MODIFIERS]
    arc_section = arc_phase
    if arc_modifiers:
        arc_section += " " + " ".join(arc_modifiers)

    user_turns = [t for t in history if t.speaker == "user"]

    # Pick response mode — weighted random creates natural rhythm.
    # After a long response, bias toward short/medium to prevent monologue streaks.
    weights = dict(_MODE_WEIGHTS[phase_key])
    if user_turns and len(user_turns[-1].text.split()) > 100:
        weights["long"] = weights["long"] * 0.2
        weights["short"] = weights["short"] + 0.3
    mode = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]
    mode_cfg = _RESPONSE_MODES[mode]
    word_lo, word_hi = mode_cfg["words"]
    word_target = random.randint(word_lo, word_hi)
    token_ceiling = mode_cfg["ceiling"]

    # Extract previous response openers to avoid repetition
    previous_openers = []
    for t in user_turns[-5:]:  # Last 5 user responses
        first_words = t.text.split()[:4]
        if first_words:
            previous_openers.append(" ".join(first_words))

    opener_warning = ""
    if previous_openers:
        opener_warning = f"""

**DO NOT start your response with any of these phrases you've already used:**
{chr(10).join(f'- "{o}..."' for o in previous_openers)}
Start differently - with a fact, a name, a date, an emotion, or a question."""

    prompt = f"""{persona.system_prompt()}

**Emotional Arc (Turn {turn_num} of ~{max_turns}):**
{arc_section}
{opener_warning}

**Length: ~{word_target} words.** Finish your thought completely — do not trail off mid-sentence.

**Conversation so far:**
{history_text}

**Your response:**"""

    response = gemini_text_sync(
        prompt, temperature=0.75, max_output_tokens=token_ceiling
    )
    return _trim_to_sentence(response.strip())


class ConversationSimulator:
    def __init__(
        self,
        max_turns: int = 20,
        persist: bool = False,
        username: str | None = None,
        skip_extraction: bool = True,
    ):
        self.max_turns = max_turns
        self.persist = persist
        self.username = username
        self.skip_extraction = skip_extraction

    def run(self, persona: Persona, ask_fn, on_progress=None, yield_progress=False):
        """Run conversation simulation.

        Args:
            persona: The persona to simulate
            ask_fn: The function to call for AI responses
            on_progress: Optional callback(turn_num, max_turns, user_text, ai_text) -> str
                        Returns SSE-formatted progress message
            yield_progress: If True, yields progress strings then final ConversationResult
        """
        logging.getLogger("httpx").setLevel(logging.WARNING)

        turns: list[Turn] = []
        user_text = persona.presenting_problem

        persona_dict = {
            "name": persona.name,
            "background": persona.background,
            "traits": [t.value for t in persona.traits],
            "attachmentStyle": persona.attachmentStyle.value,
            "presenting_problem": persona.presenting_problem,
        }

        # Look up user by username when persisting
        user_id = None
        if self.persist:
            if not self.username:
                raise ValueError("username is required when persist=True")
            user = User.query.filter_by(username=self.username).first()
            if not user:
                raise ValueError(f"User not found: {self.username}")
            user_id = user.id

        diagram = None
        if self.persist:
            diagram_data = DiagramData()
            diagram_data.ensure_chat_defaults()
            # Update default "User" person name to persona name
            for person in diagram_data.people:
                if person.get("id") == 1:
                    person["name"] = persona.name
                    break
            diagram = Diagram(
                user_id=user_id,
                name=f"Synthetic: {persona.name}",
                data=pickle.dumps(asdict(diagram_data)),
            )
            db.session.add(diagram)
            db.session.flush()

        discussion = Discussion(
            user_id=user_id,
            diagram_id=diagram.id if diagram else None,
            synthetic=self.persist,
            synthetic_persona=persona_dict if self.persist else None,
            summary=f"Synthetic: {persona.name}" if self.persist else None,
            status=DiscussionStatus.Generating if self.persist else DiscussionStatus.Pending,
        )
        db.session.add(discussion)
        db.session.flush()

        user_speaker = None
        ai_speaker = None
        if self.persist:
            user_speaker = Speaker(
                discussion_id=discussion.id,
                name=persona.name,
                type=SpeakerType.Subject,
            )
            ai_speaker = Speaker(
                discussion_id=discussion.id,
                name="AI Coach",
                type=SpeakerType.Expert,
            )
            db.session.add_all([user_speaker, ai_speaker])
            db.session.flush()
            discussion.chat_user_speaker_id = user_speaker.id
            discussion.chat_ai_speaker_id = ai_speaker.id

        db.session.commit()
        discussion_id = discussion.id

        def run_loop():
            nonlocal user_text
            turn_num = 0
            for _ in range(self.max_turns):
                turn_num += 1
                turns.append(Turn(speaker="user", text=user_text))

                # Re-fetch to avoid ObjectDeletedError after commit expires objects
                _discussion = db.session.get(Discussion, discussion_id)
                if not _discussion:
                    raise RuntimeError(
                        f"Discussion {discussion_id} was deleted during generation"
                    )

                # ask_fn creates both user and AI statements internally
                response = ask_fn(_discussion, user_text)
                ai_text = response.statement
                turns.append(Turn(speaker="ai", text=ai_text))

                _log.info(f"[{turn_num}] USER: {user_text}")
                _log.info(f"[{turn_num}] AI: {ai_text}")

                db.session.commit()

                if on_progress:
                    progress_result = on_progress(
                        turn_num, self.max_turns, user_text, ai_text
                    )
                    if yield_progress and progress_result:
                        yield progress_result

                user_text = simulate_user_response(
                    persona, turns, turn_num, self.max_turns
                )

        if yield_progress:

            def generator():
                try:
                    yield from run_loop()
                    if not self.persist:
                        db.session.delete(discussion)
                        db.session.commit()
                        yield ConversationResult(turns=turns, persona=persona)
                    else:
                        yield ConversationResult(
                            turns=turns, persona=persona, discussionId=discussion.id
                        )
                except Exception:
                    if not self.persist:
                        db.session.delete(discussion)
                        db.session.commit()
                    raise

            return generator()
        else:
            try:
                for _ in run_loop():
                    pass
            except Exception:
                if not self.persist:
                    db.session.delete(discussion)
                    db.session.commit()
                raise

            if not self.persist:
                db.session.delete(discussion)
                db.session.commit()
                return ConversationResult(turns=turns, persona=persona)

            return ConversationResult(
                turns=turns, persona=persona, discussionId=discussion.id
            )


# --- Big Five Mapping for Persona Generation ---

_BIG_FIVE_TRAITS = {
    PersonaTrait.Evasive: {"O": "low", "E": "low"},
    PersonaTrait.Oversharing: {"E": "high", "N": "high"},
    PersonaTrait.ConfusedDates: {"C": "low"},
    PersonaTrait.Defensive: {"A": "low"},
    PersonaTrait.Tangential: {"C": "low", "E": "high"},
    PersonaTrait.Terse: {"E": "low"},
    PersonaTrait.Emotional: {"N": "high"},
    PersonaTrait.Mature: {"C": "high", "O": "high", "N": "low"},
    PersonaTrait.HighFunctioning: {"C": "high", "O": "high", "N": "low"},
}

_BIG_FIVE_ATTACHMENT = {
    AttachmentStyle.Secure: {"N": "low"},
    AttachmentStyle.AnxiousPreoccupied: {"N": "high", "E": "high", "A": "high"},
    AttachmentStyle.DismissiveAvoidant: {"N": "low", "A": "low", "E": "low"},
    AttachmentStyle.FearfulAvoidant: {"N": "high", "A": "low", "E": "low"},
}

_BIG_FIVE_NAMES = {
    "O": "Openness",
    "C": "Conscientiousness",
    "E": "Extraversion",
    "A": "Agreeableness",
    "N": "Neuroticism",
}


def _derive_big_five(traits, attachment_style):
    profile = {}
    for t in traits:
        for dim, level in _BIG_FIVE_TRAITS.get(t, {}).items():
            profile[dim] = level
    for dim, level in _BIG_FIVE_ATTACHMENT.get(attachment_style, {}).items():
        if dim not in profile:
            profile[dim] = level
    return ", ".join(
        f"{profile.get(d, 'moderate')}-{n}" for d, n in _BIG_FIVE_NAMES.items()
    )


def generate_persona(traits, attachment_style, sex, age):
    """Generate a new persona via LLM. Saves to DB, returns SyntheticPersona."""
    from btcopilot.personal.models import SyntheticPersona

    existing_names = [p.name for p in SyntheticPersona.query.all()]
    deprecated_names = [p.name for p in DEPRECATED_PERSONAS]
    excluded = existing_names + deprecated_names

    big_five = _derive_big_five(traits, attachment_style)

    example = DEPRECATED_PERSONAS[0]
    example_bg = example.background[:1500]

    trait_names = [t.value for t in traits]
    categories = [c.value for c in DataCategory]

    if PersonaTrait.Terse in traits or PersonaTrait.Defensive in traits:
        style_note = (
            "The presenting problem should be SHORT and guarded — 1-2 sentences max."
        )
    elif PersonaTrait.Oversharing in traits:
        style_note = "The presenting problem should be long, rambling, with digressions and self-corrections."
    else:
        style_note = "The presenting problem should be natural and somewhat vague — 1-3 sentences."

    prompt = f"""Generate a synthetic therapy client persona. Return ONLY valid JSON.

**Parameters:**
- Sex: {sex}
- Age: {age}
- Traits: {', '.join(trait_names)}
- Attachment style: {attachment_style.value}
- Big Five profile: {big_five}

**Instructions:**
1. Choose a {sex} first name NOT in: {', '.join(excluded)}
2. Write a detailed family background with: own family, parents, siblings, grandparents, aunts/uncles, and 3-4 nodal events with emotional process descriptions (anxiety, functioning, triangles).
3. {style_note}
4. Generate data_points mapping family members to categories.
5. Ensure consistency with the Big Five profile and attachment style.

**Background format example (truncated):**
{example_bg}...

**DataPoint categories:** {', '.join(categories)}

Return JSON:
{{"name": "...", "background": "...", "presenting_problem": "...", "data_points": [{{"category": "...", "keywords": [...]}}]}}"""

    response = gemini_text_sync(prompt, temperature=0.8)

    # Parse JSON, stripping markdown code fences if present
    text = response.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        else:
            text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse generated persona JSON: {e}")

    for required in ("name", "background", "presenting_problem", "data_points"):
        if required not in data:
            raise ValueError(f"Missing field in generated persona: {required}")

    db_persona = SyntheticPersona(
        name=data["name"],
        background=data["background"],
        traits=[t.value for t in traits],
        attachment_style=attachment_style.value,
        presenting_problem=data["presenting_problem"],
        data_points=data["data_points"],
        sex=sex,
        age=age,
    )
    db.session.add(db_persona)
    db.session.flush()

    return db_persona


# --- Evaluators ---

# Robotic patterns to detect
ROBOTIC_PATTERNS = [
    # Therapist clichés from the prompt
    (r"\bit sounds like\b", "therapist_cliche"),
    (r"\bthat sounds\b", "therapist_cliche"),
    (r"\bit makes sense that\b", "therapist_cliche"),
    (r"\bthat must be (hard|difficult|frustrating)\b", "therapist_cliche"),
    (r"\bhow does that make you feel\b", "therapist_cliche"),
    (r"\btell me more\b", "vague_prompt"),
    # Verbatim echoing
    (r"^(so |it sounds like |what i('m| am) hearing is )", "echo_opener"),
    # Repetitive sentence starters (tracked separately)
]


@dataclass
class PatternMatch:
    pattern: str
    category: str
    turnIndex: int
    text: str


@dataclass
class QualityResult:
    patterns: list[PatternMatch]
    repetitiveStarters: dict[str, int]  # starter -> count
    questionsPerTurn: list[int]
    verbatimEchoRate: float
    score: float  # 0-1, higher is better

    @property
    def passed(self) -> bool:
        return self.score >= 0.7


class QualityEvaluator:
    def evaluate(self, result: ConversationResult) -> QualityResult:
        patterns = self._detect_patterns(result.turns)
        starters = self._count_starters(result.turns)
        questions = self._count_questions(result.turns)
        echo_rate = self._calculate_echo_rate(result.turns)
        score = self._calculate_score(patterns, starters, questions, echo_rate)

        return QualityResult(
            patterns=patterns,
            repetitiveStarters=starters,
            questionsPerTurn=questions,
            verbatimEchoRate=echo_rate,
            score=score,
        )

    def _detect_patterns(self, turns: list[Turn]) -> list[PatternMatch]:
        matches = []
        for i, turn in enumerate(turns):
            if turn.speaker != "ai":
                continue
            for pattern, category in ROBOTIC_PATTERNS:
                if re.search(pattern, turn.text, re.IGNORECASE):
                    matches.append(
                        PatternMatch(
                            pattern=pattern,
                            category=category,
                            turnIndex=i,
                            text=turn.text,
                        )
                    )
        return matches

    def _count_starters(self, turns: list[Turn]) -> dict[str, int]:
        starters: dict[str, int] = {}
        for turn in turns:
            if turn.speaker != "ai":
                continue
            text = turn.text.strip()
            first_sentence = re.split(r"[.!?]", text)[0].strip().lower()
            words = first_sentence.split()[:5]
            if words:
                starter = " ".join(words)
                starters[starter] = starters.get(starter, 0) + 1
        return {k: v for k, v in starters.items() if v > 1}

    def _count_questions(self, turns: list[Turn]) -> list[int]:
        counts = []
        for turn in turns:
            if turn.speaker != "ai":
                continue
            counts.append(turn.text.count("?"))
        return counts

    def _calculate_echo_rate(self, turns: list[Turn]) -> float:
        if len(turns) < 2:
            return 0.0

        echo_count = 0
        comparisons = 0

        for i in range(1, len(turns)):
            if turns[i].speaker != "ai":
                continue
            prev_user = turns[i - 1] if turns[i - 1].speaker == "user" else None
            if not prev_user:
                continue

            comparisons += 1
            user_words = set(prev_user.text.lower().split())
            ai_words = set(turns[i].text.lower().split())
            overlap = len(user_words & ai_words) / max(len(user_words), 1)
            if overlap > 0.5:
                echo_count += 1

        return echo_count / max(comparisons, 1)

    def _calculate_score(
        self,
        patterns: list[PatternMatch],
        starters: dict[str, int],
        questions: list[int],
        echo_rate: float,
    ) -> float:
        score = 1.0

        score -= len(patterns) * 0.1

        for count in starters.values():
            if count > 2:
                score -= (count - 2) * 0.05

        avg_questions = sum(questions) / max(len(questions), 1)
        if avg_questions > 3:
            score -= (avg_questions - 3) * 0.1

        score -= echo_rate * 0.3

        return max(0.0, min(1.0, score))


@dataclass
class CategoryCoverage:
    category: DataCategory
    covered: bool
    matchedKeywords: list[str]


@dataclass
class CoverageResult:
    categoryCoverage: list[CategoryCoverage]
    coverageRate: float  # 0-1, ratio of categories touched
    missedCategories: list[DataCategory]

    @property
    def passed(self) -> bool:
        return self.coverageRate >= 0.7


class CoverageEvaluator:
    def evaluate(self, result: ConversationResult) -> CoverageResult:
        if not result.persona.dataPoints:
            return CoverageResult(
                categoryCoverage=[],
                coverageRate=1.0,
                missedCategories=[],
            )

        ai_text = " ".join(t.text.lower() for t in result.turns if t.speaker == "ai")

        coverage = []
        missed = []

        for dp in result.persona.dataPoints:
            matched = [kw for kw in dp.keywords if kw.lower() in ai_text]
            covered = len(matched) > 0
            coverage.append(
                CategoryCoverage(
                    category=dp.category,
                    covered=covered,
                    matchedKeywords=matched,
                )
            )
            if not covered:
                missed.append(dp.category)

        total = len(result.persona.dataPoints)
        covered_count = sum(1 for c in coverage if c.covered)
        rate = covered_count / total if total > 0 else 1.0

        return CoverageResult(
            categoryCoverage=coverage,
            coverageRate=rate,
            missedCategories=missed,
        )


# --- Client Realism Evaluator ---

# Therapy-speak patterns that real first-session clients wouldn't use
CLIENT_THERAPY_SPEAK = [
    (r"\b(boundaries|boundary)\b", "therapy_jargon"),
    (r"\b(triggered|triggering)\b", "therapy_jargon"),
    (r"\b(codependent|codependency)\b", "therapy_jargon"),
    (r"\b(attachment style|attachment pattern)\b", "therapy_jargon"),
    (r"\b(emotional regulation|self-regulate)\b", "therapy_jargon"),
    (r"\b(inner child|core wound)\b", "therapy_jargon"),
    (r"\b(narcissis(t|tic|m))\b", "pop_psychology"),
    (r"\b(gasligh(t|ting|ted))\b", "pop_psychology"),
    (r"\b(toxic|toxicity)\b", "pop_psychology"),
    (r"\b(trauma bond|trauma response)\b", "pop_psychology"),
    (r"\b(validate|validation)\b", "therapy_jargon"),
    (r"\b(safe space|hold space)\b", "therapy_jargon"),
    (r"\b(unpack that|unpack this)\b", "therapy_jargon"),
    (r"\b(coping mechanism|coping strateg)\b", "therapy_jargon"),
    (r"\b(enmesh(ed|ment))\b", "therapy_jargon"),
    (r"\b(parentif(ied|ication))\b", "therapy_jargon"),
]

# Patterns indicating organized delivery (not how real clients talk)
ORGANIZED_DELIVERY_PATTERNS = [
    (r"(?:first|1)[,.]?\s*(?:second|2)[,.]?\s*(?:third|3)", "numbered_list"),
    (r"(?:on one hand|on the other hand)", "rhetorical_structure"),
    (r"(?:in summary|to summarize|in conclusion)", "summary_language"),
    (
        r"(?:there are (?:three|four|five|several) (?:things|reasons|issues))",
        "enumeration",
    ),
    (r"(?:let me (?:explain|tell you|walk you through))", "presentation_language"),
]


@dataclass
class ClientRealismResult:
    # Heuristic dimensions
    therapySpeakMatches: list[PatternMatch]
    organizedDeliveryMatches: list[PatternMatch]
    wordCountsPerTurn: list[int]
    avgWordCount: float
    wordCountStdDev: float
    consecutiveLongStreaks: int  # max run of turns > 80 words
    shortResponseRatio: float  # ratio of turns < 30 words (after turn 5)
    rhetoricalQuestionRatio: float  # ratio of turns ending with a question
    repeatedClosers: int  # count of closing phrases used more than once
    # LLM-scored dimensions
    emotionalArcScore: float  # 0-1, does the arc oscillate vs monotonic
    emotionalArcEvidence: str
    # Composite
    score: float  # 0-1, higher = more realistic

    @property
    def passed(self) -> bool:
        return self.score >= 0.6

    def summary(self) -> str:
        lines = [
            f"Client Realism Score: {self.score:.2f} ({'PASS' if self.passed else 'FAIL'})",
            f"  Avg words/turn: {self.avgWordCount:.0f} (std dev: {self.wordCountStdDev:.1f})",
            f"  Short response ratio (after turn 5): {self.shortResponseRatio:.0%}",
            f"  Max consecutive long streak: {self.consecutiveLongStreaks}",
            f"  Rhetorical question endings: {self.rhetoricalQuestionRatio:.0%}",
            f"  Repeated closers: {self.repeatedClosers}",
            f"  Therapy-speak matches: {len(self.therapySpeakMatches)}",
            f"  Organized delivery matches: {len(self.organizedDeliveryMatches)}",
            f"  Emotional arc score: {self.emotionalArcScore:.2f}",
            f"  Arc evidence: {self.emotionalArcEvidence}",
        ]
        return "\n".join(lines)


class ClientRealismEvaluator:
    def evaluate(self, result: ConversationResult) -> ClientRealismResult:
        user_turns = [t for t in result.turns if t.speaker == "user"]

        therapy_speak = self._detect_therapy_speak(user_turns)
        organized = self._detect_organized_delivery(user_turns)
        word_counts = [len(t.text.split()) for t in user_turns]
        avg_wc = sum(word_counts) / max(len(word_counts), 1)
        std_dev = self._std_dev(word_counts)
        long_streak = self._max_consecutive_long(word_counts)
        short_ratio = self._short_response_ratio(word_counts)
        rq_ratio = self._rhetorical_question_ratio(user_turns)
        repeated_closers = self._repeated_closers(user_turns)
        arc_score, arc_evidence = self._score_emotional_arc(result)

        score = self._calculate_score(
            therapy_speak,
            organized,
            avg_wc,
            std_dev,
            long_streak,
            short_ratio,
            rq_ratio,
            repeated_closers,
            arc_score,
            len(user_turns),
        )

        return ClientRealismResult(
            therapySpeakMatches=therapy_speak,
            organizedDeliveryMatches=organized,
            wordCountsPerTurn=word_counts,
            avgWordCount=avg_wc,
            wordCountStdDev=std_dev,
            consecutiveLongStreaks=long_streak,
            shortResponseRatio=short_ratio,
            rhetoricalQuestionRatio=rq_ratio,
            repeatedClosers=repeated_closers,
            emotionalArcScore=arc_score,
            emotionalArcEvidence=arc_evidence,
            score=score,
        )

    def _detect_therapy_speak(self, turns: list[Turn]) -> list[PatternMatch]:
        matches = []
        for i, turn in enumerate(turns):
            for pattern, category in CLIENT_THERAPY_SPEAK:
                if re.search(pattern, turn.text, re.IGNORECASE):
                    matches.append(
                        PatternMatch(
                            pattern=pattern,
                            category=category,
                            turnIndex=i,
                            text=turn.text,
                        )
                    )
        return matches

    def _detect_organized_delivery(self, turns: list[Turn]) -> list[PatternMatch]:
        matches = []
        for i, turn in enumerate(turns):
            for pattern, category in ORGANIZED_DELIVERY_PATTERNS:
                if re.search(pattern, turn.text, re.IGNORECASE):
                    matches.append(
                        PatternMatch(
                            pattern=pattern,
                            category=category,
                            turnIndex=i,
                            text=turn.text,
                        )
                    )
        return matches

    def _std_dev(self, values: list[int]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance**0.5

    def _max_consecutive_long(self, word_counts: list[int], threshold: int = 80) -> int:
        max_streak = 0
        current = 0
        for wc in word_counts:
            if wc > threshold:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    def _short_response_ratio(
        self, word_counts: list[int], threshold: int = 30
    ) -> float:
        late_counts = word_counts[5:]
        if not late_counts:
            return 0.0
        return sum(1 for wc in late_counts if wc < threshold) / len(late_counts)

    def _rhetorical_question_ratio(self, turns: list[Turn]) -> float:
        if not turns:
            return 0.0
        count = sum(1 for t in turns if t.text.rstrip().endswith("?"))
        return count / len(turns)

    def _repeated_closers(self, turns: list[Turn], window: int = 15) -> int:
        closers: list[str] = []
        for t in turns:
            words = t.text.split()
            tail = " ".join(words[-8:]).lower() if len(words) >= 8 else t.text.lower()
            tail = re.sub(r"[.!?,;\"'…]+", "", tail).strip()
            closers.append(tail)
        repeats = 0
        for i, c in enumerate(closers):
            # Check against recent closers within window
            for prev_c in closers[max(0, i - window) : i]:
                # Fuzzy: if >60% of words overlap, it's a repeat
                c_words = set(c.split())
                prev_words = set(prev_c.split())
                if not c_words or not prev_words:
                    continue
                overlap = len(c_words & prev_words) / min(len(c_words), len(prev_words))
                if overlap > 0.6:
                    repeats += 1
                    break
        return repeats

    def _score_emotional_arc(self, result: ConversationResult) -> tuple[float, str]:
        user_turns = [t for t in result.turns if t.speaker == "user"]
        if len(user_turns) < 6:
            return 0.5, "Too few turns to assess arc"

        turn_summaries = []
        for i, t in enumerate(user_turns):
            words = t.text.split()
            wc = len(words)
            if wc <= 40:
                preview = t.text
            else:
                sentences = re.split(r"(?<=[.!?])\s+", t.text)
                if len(sentences) > 2:
                    preview = sentences[0] + " [...] " + sentences[-1]
                else:
                    preview = " ".join(words[:30]) + "..."
            turn_summaries.append(f"Turn {i+1} ({wc} words): {preview}")

        transcript = "\n".join(turn_summaries)

        prompt = f"""Score this synthetic therapy client's emotional arc on realism (0.0-1.0).

A realistic arc has:
- Length variation (short AND long turns mixed throughout)
- Pull-backs: after vulnerability, the client goes brief or deflects
- Not every question lands — some get brushed off
- Emotional intensity oscillates rather than only escalating

An unrealistic arc has:
- Uniformly long responses OR monotonically increasing length
- Every turn goes deeper than the last with no resistance
- No short defensive/deflecting responses after emotional moments

Transcript (turn number, word count, content):
{transcript}

Respond with ONLY a JSON object: {{"score": 0.0-1.0, "evidence": "one sentence explanation"}}"""

        try:
            response = gemini_text_sync(prompt, temperature=0.0)
            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```\w*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            data = json.loads(cleaned)
            return float(data["score"]), str(data["evidence"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            _log.warning(f"Failed to parse emotional arc score: {e}")
            return 0.5, f"Parse error: {e}"

    def _calculate_score(
        self,
        therapy_speak: list[PatternMatch],
        organized: list[PatternMatch],
        avg_wc: float,
        std_dev: float,
        long_streak: int,
        short_ratio: float,
        rq_ratio: float,
        repeated_closers: int,
        arc_score: float,
        num_turns: int,
    ) -> float:
        score = 1.0

        score -= len(therapy_speak) * 0.05
        score -= len(organized) * 0.1

        if avg_wc > 80:
            score -= min(0.3, (avg_wc - 80) / 100)

        if num_turns >= 6 and std_dev < 20:
            score -= 0.15

        if long_streak >= 4:
            score -= min(0.2, (long_streak - 3) * 0.05)

        if num_turns > 8 and short_ratio < 0.05:
            score -= 0.1

        # Rhetorical questions: >30% of turns ending with "?" is formulaic
        if num_turns >= 6 and rq_ratio > 0.3:
            score -= min(0.15, (rq_ratio - 0.3) * 0.5)

        # Repeated closers: penalize reusing the same ending phrases
        if repeated_closers >= 2:
            score -= min(0.1, repeated_closers * 0.03)

        arc_penalty = (1.0 - arc_score) * 0.3
        score -= arc_penalty

        return max(0.0, min(1.0, score))


def run_synthetic_tests(
    ask_fn, personas: list[Persona] | None = None, conversations_per_persona: int = 2
) -> list[ConversationResult]:
    if personas is None:
        personas = PERSONAS

    simulator = ConversationSimulator()
    evaluator = QualityEvaluator()
    results = []

    for persona in personas:
        for _ in range(conversations_per_persona):
            _log.info(f"Running conversation with {persona.name}")
            result = simulator.run(persona, ask_fn)
            result.quality = evaluator.evaluate(result)
            results.append(result)
            _log.info(
                f"Completed: {len(result.turns) // 2} turns, score={result.quality.score:.2f}"
            )

    return results
