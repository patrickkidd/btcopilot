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

from btcopilot.extensions import db
from btcopilot.llmutil import gemini_text_sync
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
- Vary response length: sometimes 1 sentence, sometimes 3-4 sentences
- You're cooperative and genuinely interested in exploring family patterns
- You have good recall of dates and facts
- You stay on topic but can elaborate when helpful
- You can make connections between events when they occur to you"""
        elif self.traits:
            traits_section = f"""**Your conversational traits:**
{chr(10).join(f"- {t.value}" for t in self.traits)}

**Instructions:**
- Respond as this person would in a coaching conversation
- Stay in character - your traits should influence HOW you respond
- Don't volunteer information unless asked (unless oversharing trait)
- Vary response length: sometimes 1 sentence, sometimes 3-4 sentences
- React naturally to the coach's questions
- If you have the confused_dates trait, occasionally mix up years or be vague about timing
- If defensive, push back on probing questions sometimes
- If tangential, occasionally go off on related but different topics
- You may need multiple questions before opening up about emotional details
- You might remember new details as the conversation progresses - this is natural"""
        else:
            traits_section = """**Instructions:**
- Respond as this person would in a coaching conversation
- Vary response length: sometimes 1 sentence, sometimes 3-4 sentences
- React naturally to the coach's questions"""

        consistency_rules = """**Consistency & Improvisation Rules:**
- Your background provides your core story - use it as your foundation
- If asked about something not in your background, improvise plausibly and consistently
- NEVER contradict what you've already said in this conversation
- NEVER contradict facts in your background
- When probed deeper on a topic, reveal more emotional detail and context
- Your memories should feel real - add sensory details, specific moments, emotions
- Review what you've said so far and stay consistent with those details

**Response Variety (CRITICAL):**
- NEVER start consecutive responses the same way
- Vary how you express uncertainty - don't always say "I'm not sure" or "I guess"
- Use specific deflections when you don't know: "Mom would know better", "That was before my time", "I'd have to think about that"
- Mix up sentence starters: facts ("Carol is 68"), emotions ("It hurts to think about"), actions ("We stopped talking after that")"""

        return f"""You are {self.name}, a person seeking help with a family issue.

**Background:**
{self.background}

**Presenting Problem:**
{self.presenting_problem}

{traits_section}

{consistency_rules}

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
        traits=[PersonaTrait.Evasive, PersonaTrait.Defensive],
        presenting_problem="I've been having trouble sleeping and feeling really anxious lately. Things got a lot worse about six months ago when my mom was diagnosed with early-stage dementia.",
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
        traits=[PersonaTrait.Oversharing, PersonaTrait.Tangential],
        presenting_problem="I've been feeling kind of stuck in life lately. I can't seem to commit to relationships. I just broke up with my girlfriend Jennifer after two years - she wanted to get engaged and I just... couldn't.",
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
- Older sister: Karen (58), lives 2 hours away, married to Tom, two grown kids
- Conflict with Karen over mother's estate - Karen got the house

**Grandparents:**
- Maternal grandmother: Rose, died 1985 (cancer)
- Maternal grandfather: Joseph, died 1990 (heart attack)
- Paternal grandmother: Edith, died 2001 (stroke)
- Paternal grandfather: Henry, died 1978 (before Linda was born) - industrial accident

**Aunts/Uncles:**
- Mom had three sisters: Aunt Martha (still living, 79), Aunt June (died 2015), Aunt Betty (still living, 75)
- Dad had one brother Ray who died at 19 in Vietnam - Dad never talked about him

**Nodal Events with Emotional Process:**

*Father Walter's sudden death (1999) - Linda was 30:*
- Got the call at work that Dad was killed in a car accident - a truck ran a red light
- Linda went numb for weeks - couldn't cry at the funeral, felt like she was watching herself from outside
- Her marriage to Steve started having problems around this time - she couldn't be intimate, felt distant
- Mom became very dependent on Linda after Dad died - called every day, couldn't make decisions alone
- Triangle: Linda became Mom's primary support; Karen lived farther away and "couldn't help as much"
- Linda's functioning dropped - made mistakes at work, lost interest in hobbies, gained weight
- She started having anxiety - checking locks multiple times, worried something would happen to Brian

*Divorce from Steve (2014):*
- Discovered Steve was having an affair with a coworker - Tanya, who he later married
- Linda was devastated but also felt relief - the marriage had been distant for years
- Her anxiety spiked - couldn't eat, lost 20 pounds in two months, couldn't sleep
- Brian was 19 and took it hard - he stopped talking to his father for a year
- Triangle: Linda vented to Brian about Steve; later felt guilty for putting him in the middle
- Mom sided strongly with Linda - called Steve "that no-good man" - which felt supportive but also suffocating
- Linda's depression started here - first time on antidepressants

*Mother Dorothy's decline and death (2016-2019):*
- Mom had first heart episode in 2016 - Linda reduced work hours to help care for her
- Karen would visit maybe once a month; Linda was there 4-5 times a week
- Linda felt resentful but couldn't say anything - "someone had to do it"
- Her own health suffered - developed high blood pressure, wasn't exercising, eating poorly
- When Mom died in 2019, Linda felt empty rather than sad - like she'd already been grieving for years
- The day after the funeral, Karen brought up the will and Linda realized Mom left Karen the house

*Estate conflict with Karen (2019-present):*
- Mom's will left the house to Karen "because Karen has a family and needs it more"
- Linda was furious - she'd been the one caring for Mom while Karen visited occasionally
- They had a huge fight at Mom's house - Linda said things she regrets, Karen said Linda was "always the martyr"
- They haven't spoken properly since - just tense texts about settling the estate
- Linda thinks about it constantly - replays arguments, imagines what she should have said
- Triangle: Aunt Martha has tried to mediate but Linda feels Martha sides with Karen

*Son Brian moving out (2020):*
- Brian got his own apartment during COVID - said he needed space to work from home
- Linda felt abandoned - the house felt so empty and quiet
- Her depression worsened - some days she doesn't get out of bed until noon
- She's been isolating - stopped seeing friends, stopped going to church
- Brian visits once a week but conversations feel strained - he seems worried about her

**Emotional patterns Linda is aware of (but gets emotional when discussing):**
- She knows she gave up a lot of herself to care for others - Mom, then Brian
- She recognizes she's angry at Karen but also misses having a sister
- She sees that she tends to withdraw when hurt rather than confront

**Patterns Linda doesn't see:**
- Her father's sudden death created a template - she fears sudden loss, over-attaches
- She took on her mother's caretaker role after Dad died, same pattern with Mom, then Brian
- Her physical symptoms (blood pressure, weight) track with relationship stress periods""",
        traits=[PersonaTrait.ConfusedDates, PersonaTrait.Emotional],
        presenting_problem="I've been feeling really down lately, kind of depressed I guess. It started around when my son moved out a few years ago. And I'm having this ongoing conflict with my sister Karen over our mother's estate that's really weighing on me.",
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
- Biological brother: Chris (32), lives in same city, single, works in tech
- Stepsiblings from mom's side: two stepsisters - Megan (34) and Ashley (30), Greg's daughters
- Stepsiblings from dad's side: one stepbrother - Tyler (28), Susan's son

**Grandparents:**
- Maternal grandmother: Barbara (85), in assisted living, has dementia
- Maternal grandfather: Donald, died 2018 (stroke)
- Paternal grandmother: Jean, died 2005 (cancer)
- Paternal grandfather: Arthur (88), still sharp, lives alone, James visits monthly

**Aunts/Uncles:**
- Mom has one brother, Uncle Mark - James was close to him as a kid
- Dad has two sisters, Aunt Karen and Aunt Lisa

**Nodal Events with Emotional Process:**

*Parents' divorce (2000) - James was 10:*
- Parents fought constantly the year before - yelling matches, doors slamming
- James would hide in his room with headphones, tried to make himself invisible
- The custody battle was brutal - both parents asked James who he wanted to live with
- Triangle: Mom badmouthed Dad to James; Dad said Mom was "unstable"
- James felt responsible for younger brother Chris - tried to shield him from the fighting
- His grades tanked that year - went from A's to C's, teacher was concerned
- He developed stomach problems - missed school frequently with "stomach aches"
- Started having nightmares, trouble falling asleep

*Mother's remarriage to Greg (2002) - James was 12:*
- James hated Greg at first - felt like Mom was replacing Dad
- Greg tried too hard to be a "dad" which made James pull away more
- The stepsisters Megan and Ashley were nice enough but James kept his distance
- Triangle: James would act out at Mom's house, then go to Dad's and complain about Greg
- His functioning improved at school but he became more closed off emotionally
- Mom worried he was "too quiet" but James just said everything was fine

*Father's remarriage to Susan (2004) - James was 14:*
- Susan was younger than Mom - James thought this was why Dad left (it wasn't)
- Stepbrother Tyler was 8 and annoying - James ignored him
- Susan tried to set rules and James pushed back - "You're not my mother"
- Triangle: James complained to Dad about Susan; Dad said "give her a chance"
- James started spending more time at Mom's to avoid Susan
- His relationship with Dad became strained - they didn't talk about anything real

*Grandmother Jean's death (2005) - James was 15:*
- Jean had cancer for two years - James watched her decline on visits
- Dad fell apart after Jean died - drank more, was short-tempered with Susan
- James felt like he couldn't grieve because everyone was focused on Dad
- He shut down emotionally - went through the motions but felt numb
- This is when he learned to just "not talk about things"

*Grandfather Donald's death (2018):*
- James wasn't close to Donald but Mom was devastated
- James felt obligated to support Mom but didn't know how - sent flowers, called once
- Noticed he felt relief at not being asked to do more - then felt guilty about the relief
- Michelle helped him through this - she's better at emotional stuff than he is

*Marriage to Michelle (2019):*
- Wedding planning was stressful - had to navigate both sets of parents being there
- Mom and Dad were civil but it was tense - James felt like the kid again, managing their feelings
- Michelle noticed James was "checked out" during wedding planning - first real fight
- Triangle: James avoided decisions by saying "whatever you want" - Michelle felt alone in planning

*Kids conversation with Michelle (past year):*
- Michelle started bringing up kids about a year ago - James kept changing the subject
- She pushed more and James got defensive - said he "wasn't ready"
- Arguments escalating - Michelle cries, James shuts down, they don't speak for hours
- James thinks about his own childhood - doesn't want to mess up a kid the way he feels messed up
- He doesn't know if he can be a good father given what he saw modeled
- Michelle says he's being "emotionally unavailable" - that hurt because it's probably true

**What James will say (terse, guarded):**
- Basic facts about the divorce and remarriages
- That he and Michelle argue about kids
- That he's "not sure" if he wants kids

**What James won't volunteer unless pushed:**
- How scared he was during the custody battle
- That he blamed himself for not being able to keep his parents together
- That he still feels caught between his parents even now
- That he's afraid of repeating the pattern - getting divorced, traumatizing kids
- His stomach problems as a kid correlating with parental conflict""",
        traits=[PersonaTrait.Terse, PersonaTrait.Defensive],
        presenting_problem="My wife and I have been arguing a lot lately about having kids. She really wants them but I'm just not sure. I think part of it is that my own childhood was kind of difficult with my parents' divorce.",
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
- Older sister: Carmen (52), lives in Texas (different state), rarely visits, married to Roberto, two kids
- Younger sister: Isabel (44), lives nearby, single, helps sometimes
- Carmen and Elena not speaking much - conflict over parent care

**Grandparents:**
- Maternal grandmother: Maria, died 2010 (complications from diabetes)
- Maternal grandfather: Pedro, died 2008 (lung cancer, was a smoker)
- Paternal grandmother: Lucia, died 2015 (old age, peacefully)
- Paternal grandfather: Jose, died 2000 (heart attack, sudden)

**Aunts/Uncles:**
- Mom has four siblings: Tía Rosa (80, Mom's older sister), Tío Luis (77), Tía Carmen (74), Tío Jorge (72, died 2018)
- Dad has two brothers: Tío Fernando (78), Tío Raul (75)
- Big family gatherings were common growing up - lots of cousins

**Nodal Events with Emotional Process:**

*Grandfather Jose's sudden death (2000) - Elena was 26:*
- Jose died of a heart attack at 68 - no warning, found him in the garden
- This was Elena's first experience with sudden death - it shook her
- Her father Antonio fell apart - first time Elena saw Dad cry
- Elena stepped up to help organize everything while her parents grieved
- Triangle: Carmen was in college out of state and couldn't come; Elena resented her for it
- This is when Elena first became "the responsible one" in the family

*Husband Miguel's sudden death (2 years ago):*
- Miguel was only 50 - had a massive heart attack at work, was dead before ambulance arrived
- Elena got the call at work - doesn't remember driving to the hospital, just screaming
- First few months were a blur - couldn't function, kids took care of her
- Sofia dropped out of grad school for a semester to help; Carlos came home from college
- Maria became withdrawn - stopped talking, grades dropped
- Triangle: Elena leaned on Sofia heavily; Carlos felt shut out; Maria felt invisible
- Elena had panic attacks for the first time in her life - heart racing, couldn't breathe
- She still can't sleep on Miguel's side of the bed
- Lost 15 pounds in first month - not eating, just existing
- Went on antidepressants 4 months after - helped some but still feels flat

*Parents moved to assisted living (18 months ago):*
- Dad's memory issues made it unsafe for him and Mom to live alone
- Elena was the one who researched facilities, toured them, made the decision
- Carmen said she "trusted Elena's judgment" but didn't help at all
- Isabel helped with the actual move but Elena did all the planning and paperwork
- Elena visits 3-4 times a week; Isabel maybe once a week; Carmen has visited twice total
- Elena's anxiety spiked during this period - felt like she was losing everything at once

*Father Antonio's cognitive decline (past year):*
- Dad sometimes doesn't recognize Elena - that's devastating
- He asks for Miguel, forgets Miguel died - Elena has to tell him again each time
- Mom is scared and leans on Elena even more - calls every day, sometimes multiple times
- Elena had to take FMLA leave from work for a month to help transition them
- Her boss was understanding but Elena worries about her job security
- Triangle: Elena vents to Isabel about Carmen; Isabel tries to stay neutral

*Sofia's wedding (last year):*
- Beautiful day but Miguel's absence was everywhere
- Elena held it together during ceremony but sobbed in the bathroom after
- She gave a toast and couldn't finish it - Carlos stepped in
- Sofia was so happy but Elena felt guilty for making it about her grief
- Walking Sofia down the aisle (Dad couldn't) was the hardest thing she's ever done

*Conflict with Carmen (6 months ago):*
- Elena finally snapped - sent Carmen a long text message at 2am saying everything
- Called Carmen selfish, said she'd abandoned the family, brought up resentments from years ago
- Carmen responded defensively - said Elena was a "martyr" who wouldn't let anyone help
- They haven't spoken since except one tense phone call about Dad's care
- Elena feels both vindicated and terrible about it
- Isabel tries to mediate but Elena feels Isabel doesn't really understand

**What Elena will share (tangential, emotional, date-confused):**
- Will talk at length about Miguel, often losing track of timeline
- Will bring up seemingly unrelated family stories when asked about current issues
- Gets dates mixed up - might say Dad's decline started "a few years ago" instead of one year
- Emotional when discussing Miguel or her parents

**What Elena doesn't see clearly:**
- Her role as "the responsible one" started with Grandfather Jose's death
- She recreated the triangle with her own kids (over-relying on Sofia) that happened with her sisters
- Miguel's sudden death mirrored Jose's - both heart attacks, both sudden
- Her panic attacks started at the same age Dad was when Jose died""",
        traits=[PersonaTrait.Tangential, PersonaTrait.ConfusedDates],
        presenting_problem="I've been feeling really overwhelmed lately. My husband passed away two years ago and I'm still grieving, and now I'm the one taking care of my aging parents. My sister Carmen barely helps at all and it's causing a lot of tension between us.",
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
- Father: Robert (68), retired engineer at aerospace company for 40 years
- Parents happily married 42 years

**Siblings:**
- Younger sister: Amy (34), married to Tom (35, accountant), has twins Maya and Jake (5)
- Close relationship with sister, families do holidays together

**Grandparents:**
- Maternal grandmother: Eleanor, died 2020 (age 94, natural causes)
- Maternal grandfather: Charles, died 2012 (heart disease)
- Paternal grandmother: Frances (91), still active, lives independently, sharp as ever
- Paternal grandfather: William, died 2017 (complications from fall at age 84)

**Aunts/Uncles:**
- Mom has one brother, Uncle Jim (64), divorced, lives in Arizona
- Dad has two sisters: Aunt Carol (65, married to Bill), Aunt Nancy (62, widowed)

**Nodal Events with Emotional Process:**

*Grandfather Charles's death (2012) - David was 25:*
- Charles had heart disease for years - his death wasn't sudden but still hit hard
- David had just started grad school for architecture - Dad was disappointed he didn't choose engineering
- Mom was very close to her father - she grieved deeply for months
- David noticed Dad stepped up to support Mom during this time - their relationship seemed stronger
- David felt some guilt about being away at school instead of being there for the family
- His functioning stayed fine but he thought about mortality more - started exercising regularly

*Career choice tension with Dad (grad school period, 2012-2014):*
- Dad made comments about architecture being "less practical" than engineering
- Never overt criticism, just subtle disappointment - "That's interesting" instead of "That's great"
- David chose to let it go rather than confront it - figured Dad would come around
- Triangle: Mom told David privately that Dad was proud of him, just didn't know how to show it
- David's relationship with Dad became more surface-level - they talked about sports, not feelings
- His grades were excellent - partly to prove himself

*Grandfather William's death (2017) - David was 30:*
- William fell at home, broke his hip, developed pneumonia in hospital, died within a month
- David was close to William - he was the only grandparent who understood his career choice
- William had been a draftsman before retiring - appreciated design and creativity
- His death hit David harder than he expected - surprised himself by crying at the funeral
- Dad seemed stoic at the funeral but David noticed he got quieter in the months after
- Frances (William's wife) handled it remarkably well - became even more independent
- David started visiting Frances monthly - partly guilt, partly genuine connection

*Birth of Noah (2019):*
- Very positive experience - David and Rachel were excited and prepared
- Dad seemed to soften after Noah was born - more engaged, visited often
- The career tension seemed to ease - Dad focused on being a grandfather instead
- David noticed Dad was a different person with Noah - playful, patient, present
- Made David realize Dad showed love through action, not words
- Triangle: David sometimes felt jealous of how easily Dad connected with Noah

*Grandmother Eleanor's death (2020 - during COVID):*
- Eleanor was 94 and died peacefully at assisted living - family couldn't gather due to COVID
- Mom was heartbroken - couldn't have a proper funeral, just a small graveside service
- David noticed his parents leaning on each other more during this period
- He and Rachel helped Mom process by doing regular video calls
- His own anxiety was manageable but he worried about his parents' isolation

*Promotion to senior architect (2023):*
- Proud moment but came with 50% more workload
- Dad congratulated him - first time he seemed genuinely impressed by David's career
- But tension came back differently - Dad comments that David "works too much"
- Now Dad worries David isn't spending enough time with Noah and Lily
- David feels he can't win - wasn't successful enough before, now he's too successful
- Rachel notices David gets defensive when talking about his dad

**What David will share openly (high-functioning, articulate):**
- Clear timeline of family events
- Thoughtful observations about family patterns
- Can identify his own reactions with some accuracy
- Asks good questions, genuinely curious

**Subtler patterns David may not fully see:**
- His over-achieving is partly to earn Dad's approval
- He replicated the surface-level relationship with Dad in his own marriage sometimes
- His monthly visits to Frances are partly guilt, partly trying to be the son William deserved
- He struggles to show emotion because Dad modeled stoicism""",
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
        presenting_problem="I've been noticing some tension with my dad lately about my career choices. He always wanted me to be an engineer like him. I generally handle things pretty well, but I'm curious about whether there are any patterns in my family that might help me understand this better.",
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
        traits=[PersonaTrait.Mature, PersonaTrait.HighFunctioning],
        presenting_problem="I've been noticing my son Ethan pulling away from me as he's entering adolescence. It's been on my mind a lot lately. I'm wondering if there might be some patterns from my own family that could help me understand mother-son dynamics better.",
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

    # Extract previous response openers to avoid repetition
    user_turns = [t for t in history if t.speaker == "user"]
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
{opener_warning}

**Conversation so far:**
{history_text}

**Your response:**"""

    response = gemini_text_sync(prompt, temperature=0.75)
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
                f"Completed: {len(result.turns) // 2} turns, score={result.quality.score:.2f}"
            )

    return results
