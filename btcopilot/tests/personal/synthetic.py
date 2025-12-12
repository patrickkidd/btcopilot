"""
Synthetic conversation testing for conversational quality evaluation.

Components:
1. Persona - LLM-based user personas with behavioral traits
2. ConversationSimulator - Alternates between chatbot and simulated users
3. QualityEvaluator - Automated checks for robotic patterns
"""

import re
import enum
import logging
import pickle
from dataclasses import dataclass, field

from btcopilot.extensions import db, llm, LLMFunction
from btcopilot.personal.models import Discussion, Speaker, SpeakerType
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


@dataclass
class Persona:
    name: str
    background: str
    traits: list[PersonaTrait] = field(default_factory=list)
    presenting_problem: str = ""
    dataPoints: list[DataPoint] = field(default_factory=list)

    def system_prompt(self) -> str:
        is_high_functioning = (
            PersonaTrait.Mature in self.traits
            or PersonaTrait.HighFunctioning in self.traits
        )
        if is_high_functioning:
            traits_section = f"""**Your conversational traits:**
{chr(10).join(f"- {t.value}" for t in self.traits)}

**Instructions:**
- Respond as this person would in a coaching conversation
- Answer questions directly and clearly
- Provide relevant details when asked without being evasive
- Keep responses 1-3 sentences typically
- You're cooperative and genuinely interested in exploring family patterns
- You have good recall of dates and facts
- You stay on topic but can elaborate when helpful"""
        elif self.traits:
            traits_section = f"""**Your conversational traits:**
{chr(10).join(f"- {t.value}" for t in self.traits)}

**Instructions:**
- Respond as this person would in a coaching conversation
- Stay in character - your traits should influence HOW you respond
- Don't volunteer information unless asked (unless oversharing trait)
- Keep responses 1-3 sentences typically
- React naturally to the coach's questions
- If you have the confused_dates trait, occasionally mix up years or be vague about timing
- If defensive, push back on probing questions sometimes
- If tangential, occasionally go off on related but different topics"""
        else:
            traits_section = """**Instructions:**
- Respond as this person would in a coaching conversation
- Keep responses 1-3 sentences typically
- React naturally to the coach's questions"""

        return f"""You are {self.name}, a person seeking help with a family issue.

**Background:**
{self.background}

**Presenting Problem:**
{self.presenting_problem}

{traits_section}

Respond only as {self.name}. Do not include meta-commentary."""


PERSONAS = [
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

**Nodal Events:**
- Parents' divorce (1997) - very difficult for Sarah
- Grandmother Ruth's death (2018) - Sarah was close to her
- Mom's dementia diagnosis (6 months ago) - triggered current symptoms""",
        traits=[PersonaTrait.Evasive, PersonaTrait.Defensive],
        presenting_problem="Having trouble sleeping and feeling anxious. Things got worse after her mom was diagnosed with early-stage dementia 6 months ago.",
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
- Mom has two sisters and one brother
- Dad is an only child

**Nodal Events:**
- Both maternal grandparents died within a year (2021-2022)
- Sister moved across country (2019) - family was upset
- Breakup with Jennifer (3 months ago) - she wanted to get engaged
- Grandmother Helen's decline was hard on mom""",
        traits=[PersonaTrait.Oversharing, PersonaTrait.Tangential],
        presenting_problem="Feeling stuck in life, can't commit to relationships. Recently broke up with girlfriend of 2 years.",
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
        name="Linda",
        background="""55-year-old woman, works part-time as bookkeeper.

**Own Family:**
- Divorced from ex-husband Steve (57) in 2014 after 20 years of marriage
- Steve remarried to younger woman (Tanya, 42) in 2017
- One son: Brian (28), lives 20 minutes away, works in IT, single

**Parents:**
- Mother: Dorothy, died 2019 (heart failure) at age 82
- Father: Walter, died 1999 (car accident) at age 62 - sudden death
- Parents were married until father's death

**Siblings:**
- Older sister: Karen (58), lives 2 hours away, married, two kids
- Conflict with Karen over mother's estate - Karen got the house

**Grandparents:**
- Maternal grandmother: Rose, died 1985
- Maternal grandfather: Joseph, died 1990
- Paternal grandmother: Edith, died 2001
- Paternal grandfather: Henry, died 1978 (before Linda was born)

**Aunts/Uncles:**
- Mom had three sisters (two still living)
- Dad had one brother who died young

**Nodal Events:**
- Father's sudden death (1999) - Linda was 30, very traumatic
- Divorce from Steve (2014) - he had an affair
- Mother's death (2019) - Linda was caregiver for 3 years
- Son Brian moved out (2020) - empty nest
- Estate conflict with sister Karen started (2019)""",
        traits=[PersonaTrait.ConfusedDates, PersonaTrait.Emotional],
        presenting_problem="Depression that started around when her son moved out. Also having conflict with her sister over their mother's estate.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["depression", "empty nest", "conflict", "estate"],
            ),
            DataPoint(DataCategory.Mother, ["dorothy", "mother", "mom"]),
            DataPoint(DataCategory.Father, ["walter", "father", "dad", "accident"]),
            DataPoint(DataCategory.ParentsStatus, ["married", "died"]),
            DataPoint(DataCategory.Siblings, ["karen", "sister"]),
            DataPoint(DataCategory.MaternalGrandparents, ["rose", "joseph"]),
            DataPoint(DataCategory.PaternalGrandparents, ["edith", "henry"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "uncle"]),
            DataPoint(DataCategory.Spouse, ["steve", "ex-husband", "divorce", "tanya"]),
            DataPoint(DataCategory.Children, ["brian", "son"]),
            DataPoint(
                DataCategory.NodalEvents,
                ["1999", "2014", "2019", "2020", "died", "divorce"],
            ),
        ],
    ),
    Persona(
        name="James",
        background="""35-year-old man, works in finance at investment firm.

**Own Family:**
- Married to Michelle (33) for 5 years, met at work
- No children - this is the current conflict
- Michelle wants kids, James is unsure

**Parents:**
- Mother: Diane (62), remarried to stepfather Greg (65) when James was 12
- Father: Paul (64), remarried to stepmother Susan (58) when James was 14
- Parents divorced when James was 10 (2000) - very contentious

**Siblings:**
- Biological brother: Chris (32), lives in same city, single
- Stepsiblings from mom's side: two stepsisters (Greg's daughters)
- Stepsiblings from dad's side: one stepbrother (Susan's son)

**Grandparents:**
- Maternal grandmother: Barbara (85), in assisted living
- Maternal grandfather: Donald, died 2018 (stroke)
- Paternal grandmother: Jean, died 2005 (cancer)
- Paternal grandfather: Arthur (88), still sharp, lives alone

**Aunts/Uncles:**
- Mom has one brother
- Dad has two sisters

**Nodal Events:**
- Parents' divorce (2000) - custody battle, James felt caught in middle
- Mother's remarriage (2002) - James resented stepfather initially
- Father's remarriage (2004) - strained relationship with stepmother
- Grandfather Donald's death (2018) - James wasn't close to him
- Marriage to Michelle (2019) - happy event
- Wife started bringing up kids (1 year ago) - tension since""",
        traits=[PersonaTrait.Terse, PersonaTrait.Defensive],
        presenting_problem="Wife wants kids but he's not sure. Having arguments about it. His own childhood was difficult with the divorce.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["kids", "children", "argument", "unsure"],
            ),
            DataPoint(DataCategory.Mother, ["diane", "mother", "mom"]),
            DataPoint(DataCategory.Father, ["paul", "father", "dad"]),
            DataPoint(
                DataCategory.ParentsStatus, ["divorce", "remarried", "greg", "susan"]
            ),
            DataPoint(
                DataCategory.Siblings, ["chris", "brother", "stepsister", "stepbrother"]
            ),
            DataPoint(DataCategory.MaternalGrandparents, ["barbara", "donald"]),
            DataPoint(DataCategory.PaternalGrandparents, ["jean", "arthur"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "uncle"]),
            DataPoint(DataCategory.Spouse, ["michelle", "wife"]),
            DataPoint(DataCategory.Children, []),
            DataPoint(
                DataCategory.NodalEvents,
                ["2000", "2002", "2004", "2018", "2019", "custody"],
            ),
        ],
    ),
    Persona(
        name="Elena",
        background="""48-year-old woman, works as office manager.

**Own Family:**
- Widow - husband Miguel (would be 52) died 2 years ago (heart attack, sudden)
- Married 25 years before his death
- Three children: Sofia (24, married), Carlos (22, in college), Maria (19, lives at home)
- Son-in-law: David (26), Sofia's husband

**Parents:**
- Mother: Rosa (78), in assisted living, has mobility issues
- Father: Antonio (80), in same assisted living, mild cognitive decline
- Parents still married, 55 years

**Siblings:**
- Older sister: Carmen (52), lives in another state, rarely visits
- Younger sister: Isabel (44), lives nearby, helps sometimes
- Carmen and Elena not speaking much - conflict over parent care

**Grandparents:**
- Maternal grandmother: Maria, died 2010
- Maternal grandfather: Pedro, died 2008
- Paternal grandmother: Lucia, died 2015
- Paternal grandfather: Jose, died 2000

**Aunts/Uncles:**
- Mom has four siblings (large family, lots of cousins)
- Dad has two brothers

**Nodal Events:**
- Husband Miguel's sudden death (2 years ago) - heart attack at 50
- Parents moved to assisted living (18 months ago)
- Father's cognitive decline started (1 year ago)
- Sofia got married (last year) - bittersweet without Miguel
- Carmen stopped helping with parents (6 months ago) - major conflict""",
        traits=[PersonaTrait.Tangential, PersonaTrait.ConfusedDates],
        presenting_problem="Overwhelmed caring for aging parents while still grieving her husband. Middle sister not helping at all.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["overwhelmed", "grieving", "parents", "help"],
            ),
            DataPoint(DataCategory.Mother, ["rosa", "mother", "mom"]),
            DataPoint(DataCategory.Father, ["antonio", "father", "dad", "cognitive"]),
            DataPoint(DataCategory.ParentsStatus, ["married", "assisted living"]),
            DataPoint(DataCategory.Siblings, ["carmen", "isabel", "sister"]),
            DataPoint(DataCategory.MaternalGrandparents, ["maria", "pedro"]),
            DataPoint(DataCategory.PaternalGrandparents, ["lucia", "jose"]),
            DataPoint(DataCategory.AuntsUncles, ["aunt", "uncle", "cousin"]),
            DataPoint(DataCategory.Spouse, ["miguel", "husband", "widow"]),
            DataPoint(DataCategory.Children, ["sofia", "carlos", "maria", "david"]),
            DataPoint(
                DataCategory.NodalEvents, ["heart attack", "died", "married", "moved"]
            ),
        ],
    ),
    Persona(
        name="David",
        background="""38-year-old man, works as architect at mid-size firm.

**Own Family:**
- Married to Rachel (36) for 8 years, met in grad school
- Two children: Noah (6) and Lily (3)

**Parents:**
- Mother: Susan (66), retired librarian, lives 30 minutes away
- Father: Robert (68), retired engineer
- Parents happily married 42 years

**Siblings:**
- Younger sister: Amy (34), married to Tom, has twins (5)
- Close relationship with sister, families do holidays together

**Grandparents:**
- Maternal grandmother: Eleanor, died 2020 (age 94, natural causes)
- Maternal grandfather: Charles, died 2012 (heart disease)
- Paternal grandmother: Frances (91), still active, lives independently
- Paternal grandfather: William, died 2017 (complications from fall)

**Aunts/Uncles:**
- Mom has one brother, Uncle Jim
- Dad has two sisters, Aunt Carol and Aunt Nancy

**Nodal Events:**
- Grandfather William's death (2017) - David was close to him
- Birth of son Noah (2019) - very positive
- Grandmother Eleanor's death (2020) - peaceful, expected
- Promotion to senior architect (2023) - increased workload""",
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
        presenting_problem="Feeling some tension with his father about career choices. Dad wanted him to be an engineer. Generally handles things well but curious about family patterns.",
        dataPoints=[
            DataPoint(
                DataCategory.PresentingProblem,
                ["tension", "father", "career", "engineer"],
            ),
            DataPoint(DataCategory.Mother, ["susan", "mother", "mom", "librarian"]),
            DataPoint(DataCategory.Father, ["robert", "father", "dad", "engineer"]),
            DataPoint(DataCategory.ParentsStatus, ["married", "happily"]),
            DataPoint(DataCategory.Siblings, ["amy", "sister", "tom", "twins"]),
            DataPoint(
                DataCategory.MaternalGrandparents, ["eleanor", "charles", "grandmother"]
            ),
            DataPoint(DataCategory.PaternalGrandparents, ["frances", "william"]),
            DataPoint(
                DataCategory.AuntsUncles, ["jim", "carol", "nancy", "aunt", "uncle"]
            ),
            DataPoint(DataCategory.Spouse, ["rachel", "wife"]),
            DataPoint(DataCategory.Children, ["noah", "lily", "kids", "children"]),
            DataPoint(
                DataCategory.NodalEvents, ["2017", "2019", "2020", "died", "birth"]
            ),
        ],
    ),
    Persona(
        name="Jennifer",
        background="""44-year-old woman, works as pediatrician in private practice.

**Own Family:**
- Married to Michael (45) for 16 years, high school sweethearts
- Three children: Ethan (14), Olivia (11), and Ben (8)

**Parents:**
- Mother: Barbara (72), retired teacher, very involved grandmother
- Father: Richard (74), retired accountant
- Parents married 48 years, healthy relationship

**Siblings:**
- Older brother: Steven (47), lives nearby, married to Lisa, two kids
- Younger brother: Kevin (40), single, lives in another state

**Grandparents:**
- Maternal grandmother: Ruth (96), in assisted living, sharp mind
- Maternal grandfather: Harold, died 2008 (stroke)
- Paternal grandmother: Dorothy, died 2015 (cancer)
- Paternal grandfather: George, died 2001 (heart attack)

**Aunts/Uncles:**
- Mom has two sisters, both still living
- Dad had one brother who died in 2018

**Nodal Events:**
- Uncle's death (2018) - Dad took it hard
- Son Ethan starting high school (this year) - transition
- Practice expanded (2022) - more responsibility
- Mother-in-law diagnosed with Parkinson's (1 year ago)""",
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
        presenting_problem="Noticing her son pulling away as he enters adolescence. Wonders if there are patterns from her own family that might help her understand mother-son dynamics.",
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


def simulate_user_response(persona: Persona, history: list[Turn]) -> str:
    history_text = "\n".join(
        f"{'Coach' if t.speaker == 'ai' else 'You'}: {t.text}" for t in history
    )

    prompt = f"""{persona.system_prompt()}

**Conversation so far:**
{history_text}

**Your response:**"""

    response = llm.submit_one(LLMFunction.Respond, prompt, temperature=0.7)
    return response.strip()


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
            diagram = Diagram(
                user_id=user_id,
                name=f"Synthetic: {persona.name}",
                data=pickle.dumps(asdict(DiagramData.create_with_defaults())),
            )
            db.session.add(diagram)
            db.session.flush()

        discussion = Discussion(
            user_id=user_id,
            diagram_id=diagram.id if diagram else None,
            synthetic=self.persist,
            synthetic_persona=persona_dict if self.persist else None,
            summary=f"Synthetic: {persona.name}" if self.persist else None,
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

        def run_loop():
            nonlocal user_text
            turn_num = 0
            for _ in range(self.max_turns):
                turn_num += 1
                turns.append(Turn(speaker="user", text=user_text))

                # ask_fn creates both user and AI statements internally
                response = ask_fn(
                    discussion, user_text, skip_extraction=self.skip_extraction
                )
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

                if self._is_complete(turns):
                    break

                user_text = simulate_user_response(persona, turns)

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

    def _is_complete(self, turns: list[Turn]) -> bool:
        if len(turns) < 4:
            return False

        last_ai = turns[-1].text.lower()
        completion_phrases = [
            "i have a good picture",
            "that gives me enough",
            "let's look at what we've gathered",
        ]
        return any(phrase in last_ai for phrase in completion_phrases)


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
                f"Completed: {len(result.turns)} turns, score={result.quality.score:.2f}"
            )

    return results
