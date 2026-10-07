"""Every write to the record has a hook, and every hook has a topic or is
named as having none, so a new event kind, fact or field cannot slip out of
the dashboards' topic panels unseen."""

from dataclasses import fields

from btcopilot import topics
from btcopilot.schema import EventKind, Fact, NotedFact, Person, RelationshipKind


def hooks() -> set[str]:
    return {
        *(f"kind:{k.value}" for k in EventKind),
        *(f"item:{f.value}" for f in NotedFact),
        *(f"fact:{f.value}" for f in Fact),
        *(f"relationship:{k.value}" for k in RelationshipKind),
        *(f"shift:{v}" for v in ("symptom", "anxiety", "functioning")),
        *(f"person:{f.name}" for f in fields(Person) if f.name != "id"),
        "person:add",
        "person:remove",
        "pair_bond",
        "emotion",
    }


def test_every_hook_has_a_topic_or_is_named_as_having_none():
    # R-0814, R-0517
    mapped = {hook for hook, _ in topics.TOPICS} | set(topics.NO_TOPIC)
    assert hooks() - mapped == set()


def test_no_hook_both_has_a_topic_and_none():
    # R-0814
    assert {hook for hook, _ in topics.TOPICS} & set(topics.NO_TOPIC) == set()


def test_the_sql_copy_holds_every_pair():
    # R-0814
    sql = topics.values()
    assert sql.startswith("topic_map(hook, topic) as (values ")
    assert sql.count("('") == len(topics.TOPICS)
