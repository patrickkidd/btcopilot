"""What a write to the record is about, for the dashboards' topic panels.

Each write gives one or more hooks: `kind:<event kind>`, `item:<noted fact>`,
`shift:<variable>` and `relationship:<kind>` from the event it touches,
`person:<field>` or `person:add` / `person:remove`, `pair_bond`, `emotion`, and
`fact:<fact>` from a fact question. A hook maps to its topics here; a hook in
NO_TOPIC, and a write with no hook, counts as no topic. Each panel that groups
by topic carries this map as `topic_map(hook, topic) as (values ...)`, and a
test holds that copy equal to TOPICS.
"""

PARTNERS = "Partners"
CHILDREN = "Children and births"
DEATHS = "Deaths"
HEALTH = "Health and symptoms"
WORK = "Work and livelihood"
SCHOOL = "School"
PLACES = "Moves and places"
CONTACT = "Contact, closeness and distance"
DOING = "How people were doing"
HARD = "Hard times"
WHO = "Who is who"
NONE = "no topic"

RELATIONSHIPS = (
    "fusion", "conflict", "distance", "overfunctioning", "underfunctioning",
    "projection", "defined-self", "toward", "away", "inside", "outside", "cutoff",
)  # fmt: skip

TOPICS = (
    *((hook, PARTNERS) for hook in (
        "kind:bonded", "kind:married", "kind:separated", "kind:divorced",
        "pair_bond", "fact:met", "fact:marriages",
    )),
    *((hook, CHILDREN) for hook in (
        "kind:birth", "kind:adopted", "fact:birth_date", "fact:children",
        "fact:order", "fact:sex", "person:parents", "person:gender",
    )),
    *((hook, DEATHS) for hook in (
        "kind:death", "fact:alive", "fact:death_date", "fact:cause_of_death",
    )),
    *((hook, HEALTH) for hook in ("item:health", "shift:symptom", "fact:health")),
    *((hook, WORK) for hook in ("item:work", "fact:work", "fact:life_course")),
    *((hook, SCHOOL) for hook in ("item:schooling", "fact:schooling")),
    *((hook, PLACES) for hook in ("item:places", "fact:places")),
    *((f"relationship:{kind}", CONTACT) for kind in RELATIONSHIPS),
    ("emotion", CONTACT),
    ("fact:contact", CONTACT),
    ("shift:anxiety", DOING),
    ("shift:functioning", DOING),
    ("fact:stress", HARD),
    ("fact:most_going_on", HARD),
    *((hook, WHO) for hook in (
        "person:add", "person:remove", "person:name", "person:parents",
        "fact:name", "fact:parents",
    )),
)  # fmt: skip

NO_TOPIC = (
    "kind:shift",
    "kind:noted",
    "person:last_name",
    "person:notes",
    "person:confidence",
    "person:primary",
)


def values() -> str:
    """The map as the SQL each topic panel pastes in."""
    rows = ", ".join(f"('{hook}', '{topic}')" for hook, topic in TOPICS)
    return f"topic_map(hook, topic) as (values {rows})"
