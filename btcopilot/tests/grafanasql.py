"""A panel's SQL as Grafana's Postgres data source sends it, and a small
dataset to run every board on, so a query that fails on Postgres fails here
and not on the hosted board.

`expand` writes out the time macros and the board's variables the way Grafana
does; `FRAGMENTS` holds the shared tables the first-wave panels open with
(the canonical copy the panels paste); `build` writes the dataset whose
expected values the dashboard tests work out by hand from the rules.
"""

import datetime
import json
import pickle
import re

from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.models import (
    Diagram,
    Discussion,
    ModelCall,
    Observation,
    ProductEvent,
    Speaker,
    Statement,
    TurnEvent,
    User,
)
from btcopilot.models.change import Author, Change
from btcopilot.models.interaction import Interaction, InteractionKind
from btcopilot.models.modelcall import Purpose
from btcopilot.models.observation import ObservationKind
from btcopilot.models.report import Report, ReportKind, ReportStatus
from btcopilot.models.speaker import SpeakerType
from btcopilot.models.statement import StatementKind
from btcopilot.schema import ItemKind

SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
CALL = re.compile(r"\$__(\w+)\(")
SELECT = re.compile(r"select\b", re.I)
WORD = re.compile(r"\w")
VARIABLE = re.compile(r"\$\{([A-Za-z]\w*)(?::(\w+))?\}|\$([A-Za-z]\w*)")


def _stamp(at: datetime.datetime) -> str:
    return f"'{at.strftime('%Y-%m-%dT%H:%M:%SZ')}'"


def _closing(sql: str, start: int) -> int:
    depth = 1
    for i in range(start, len(sql)):
        depth += {"(": 1, ")": -1}.get(sql[i], 0)
        if depth == 0:
            return i
    raise ValueError(f"unclosed macro at {start}: {sql[start - 20:start + 40]}")


def _macro(name: str, args: str, start, end) -> str:
    if name == "timeFilter":
        return f"{args} BETWEEN {_stamp(start)} AND {_stamp(end)}"
    if name == "timeFrom":
        return _stamp(start)
    if name == "timeTo":
        return _stamp(end)
    if name in ("timeGroup", "timeGroupAlias"):
        column, interval = (a.strip() for a in args.rsplit(",", 1))
        interval = interval.strip("'")
        step = int(interval[:-1]) * SECONDS[interval[-1]]
        group = f"floor(extract(epoch from {column})/{step})*{step}"
        return f'{group} AS "time"' if name == "timeGroupAlias" else group
    raise KeyError(f"no such macro: $__{name}")


def _quoted(values) -> str:
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in values)


def _variable(value, form: str | None) -> str:
    many = isinstance(value, (list, tuple))
    if form == "sqlstring" or (form is None and many):
        return _quoted(value if many else [value])
    if form in (None, "raw", "csv"):
        return ",".join(map(str, value)) if many else str(value)
    raise KeyError(f"no such variable format: {form}")


def expand(sql: str, start, end, variables: dict) -> str:
    """The macros $__timeFilter, $__timeGroup(Alias), $__timeFrom and
    $__timeTo, then each `$name`, `${name}` and `${name:sqlstring}`. A list
    value is a multi-value variable: quoted and joined with commas, as Grafana
    sends it to a SQL data source."""
    out, at = [], 0
    for found in CALL.finditer(sql):
        if found.start() < at:
            continue
        close = _closing(sql, found.end())
        out += [
            sql[at : found.start()],
            _macro(found[1], sql[found.end() : close], start, end),
        ]
        at = close + 1
    sql = "".join(out) + sql[at:]
    return VARIABLE.sub(
        lambda m: _variable(variables[m[1] or m[3]], m[2]),
        sql,
    )


FRAGMENTS = r"""
real_dg as (select dg.id as diagram_id, dg.user_id from diagrams dg join users u on u.id = dg.user_id
            where not dg.scratch and u.username not like 'claude-test%'),
sit as (select d.id as sitting_id, d.user_id, d.diagram_id, min(s.created_at) as started, max(s.created_at) as ended,
               row_number() over w as nth, lead(min(s.created_at)) over w as next_started
        from discussions d join real_dg r on r.diagram_id = d.diagram_id
        join statements s on s.discussion_id = d.id and s.kind::text = 'turn'
        join speakers sp on sp.id = s.speaker_id
        where not d.synthetic and d.kind::text = 'chat'
        group by d.id, d.user_id, d.diagram_id having bool_or(sp.type::text = 'Subject')
        window w as (partition by d.user_id order by min(s.created_at))),
msg as (select s.id as statement_id, s.discussion_id as sitting_id, s.turn_id, s.created_at, s.text, s.prompt_version,
               case sp.type::text when 'Subject' then 'person' else 'coach' end as who,
               row_number() over (partition by s.discussion_id order by s."order", s.id) as pos
        from statements s join speakers sp on sp.id = s.speaker_id join sit on sit.sitting_id = s.discussion_id
        where s.kind::text = 'turn'),
turn as (select m.turn_id, m.sitting_id, m.statement_id as reply_id, m.created_at as at, m.text,
                coalesce(m.prompt_version, 'none') as prompt_version,
                row_number() over (partition by m.sitting_id order by m.pos) as idx
         from msg m where m.who = 'coach' and m.turn_id is not null),
delta as (select dc.id as change_id, dc.diagram_id, dc.turn_id, dc.statement_id, dc.author::text as author, dc.created_at,
                 x.o, x.d->>'item_kind' as item_kind, x.d->>'item_id' as item_id, x.d->>'field' as field,
                 x.d->'before' as before, x.d->'after' as after,
                 case when x.d->>'field' is null and jsonb_typeof(x.d->'after') = 'object' then 'add'
                      when x.d->>'field' is null then 'remove' else 'set' end as op
          from diagram_changes dc join real_dg r on r.diagram_id = dc.diagram_id
          cross join lateral jsonb_array_elements(dc.deltas) with ordinality as x(d, o)),
fieldval as (select dl.diagram_id, dl.item_kind, dl.item_id, dl.change_id, dl.o, kv.key as field, kv.value as val
             from delta dl cross join lateral jsonb_each(case when dl.op = 'add' then dl.after
                                                    else jsonb_build_object(dl.field, dl.after) end) kv
             where dl.op in ('add','set')),
cur as (select distinct on (diagram_id, item_kind, item_id, field) diagram_id, item_kind, item_id, field, val
        from fieldval order by diagram_id, item_kind, item_id, field, change_id desc, o desc),
removed as (select diagram_id, item_kind, item_id from (
              select distinct on (diagram_id, item_kind, item_id) diagram_id, item_kind, item_id, op from delta
              where op in ('add','remove') order by diagram_id, item_kind, item_id, change_id desc, o desc) x
            where op = 'remove'),
person as (select diagram_id, item_id as person_id,
                  max(val#>>'{}') filter (where field='name') as name,
                  max(val#>>'{}') filter (where field='last_name') as last_name,
                  max(val#>>'{}') filter (where field='parents') as parents,
                  max(val#>>'{}') filter (where field='gender') as gender
           from cur c where item_kind = 'person'
             and not exists (select 1 from removed x where (x.diagram_id,x.item_kind,x.item_id)=(c.diagram_id,c.item_kind,c.item_id))
           group by 1,2),
bond as (select diagram_id, item_id as bond_id, max(val#>>'{}') filter (where field='person_a') as person_a,
                max(val#>>'{}') filter (where field='person_b') as person_b
         from cur c where item_kind='pair_bond' and not exists (select 1 from removed x where (x.diagram_id,x.item_kind,x.item_id)=(c.diagram_id,c.item_kind,c.item_id)) group by 1,2),
event_state as (select diagram_id, item_id as event_id,
                max(val#>>'{}') filter (where field='kind') as kind, max(val#>>'{}') filter (where field='item') as item,
                max(val#>>'{}') filter (where field='symptom') as symptom, max(val#>>'{}') filter (where field='anxiety') as anxiety,
                max(val#>>'{}') filter (where field='functioning') as functioning, max(val#>>'{}') filter (where field='relationship') as relationship,
                max(val#>>'{}') filter (where field='person') as person, max(val#>>'{}') filter (where field='spouse') as spouse,
                max(val#>>'{}') filter (where field='child') as child, max(val#>>'{}') filter (where field='dateTime') as date_time
                from cur where item_kind='event' group by 1,2),
parent_of as (select p.diagram_id, p.person_id as child, unnest(array[b.person_a, b.person_b]) as parent
              from person p join bond b on b.diagram_id = p.diagram_id and b.bond_id = p.parents),
up (diagram_id, person_id, gen, side) as (
   select diagram_id, '1', 0, 'own' from real_dg
   union all
   select u.diagram_id, po.parent, u.gen + 1,
          case when u.gen > 0 then u.side when pp.gender = 'female' then 'mother''s line'
               when pp.gender = 'male' then 'father''s line' else 'a parent''s line' end
   from up u join parent_of po on po.diagram_id = u.diagram_id and po.child = u.person_id
   left join person pp on pp.diagram_id = po.diagram_id and pp.person_id = po.parent
   where u.gen < 5 and po.parent is not null),
kin_all as (
   select diagram_id, person_id, gen, side, case gen when 0 then 'self' when 1 then 'parent' when 2 then 'grandparent' else 'great-grandparent or above' end as link from up
   union all select b.diagram_id, case when b.person_a='1' then b.person_b else b.person_a end, 0, 'partner''s', 'partner' from bond b where '1' in (b.person_a, b.person_b)
   union all select p.diagram_id, p.person_id, 0, 'own', 'sibling' from person p join person me on me.diagram_id=p.diagram_id and me.person_id='1' where p.parents = me.parents and p.person_id <> '1'
   union all select p.diagram_id, p.person_id, -1, 'own', 'child' from person p join bond b on b.diagram_id=p.diagram_id and b.bond_id=p.parents where '1' in (b.person_a, b.person_b)),
kin as (select distinct on (diagram_id, person_id) * from kin_all order by diagram_id, person_id, abs(gen), link),
wrote as (select te.turn_id from turn_events te where te.kind='tool_call' and te.payload->>'refusal' is null
            and te.payload->>'name' in ('edit_person','edit_pair_bond','edit_event','edit_cluster','merge_people','remove','undo')
          union select dl.turn_id from delta dl where dl.author='coach' and dl.item_kind in ('person','event','pair_bond','emotion')),
objection(phrase) as (values ('that''s not what i said'),('that''s not right'),('i didn''t say'),('you''ve got that wrong'),
                             ('why are you asking'),('stop asking'),('i already told you'),('check your information')),
said as (select m.*, lower(regexp_replace(translate(m.text, '‘’', ''''''), '(^|[^A-Za-z])''|''([^A-Za-z]|$)', '\1 \2', 'g')) as t
         from msg m where m.who='person' and m.text not like 'That doesn''t fit: [[impression:%'),
word_hit as (select s.statement_id, o.phrase from said s join objection o
             on s.t ~ ('(^|[^a-z0-9''])' || o.phrase || '($|[^a-z0-9''])')
             union
             select s.statement_id, 'no, with a new date or name' from said s
             cross join lateral (select c.text from msg c where c.sitting_id=s.sitting_id and c.who='coach' and c.pos<s.pos order by c.pos desc limit 1) pc(before)
             cross join lateral regexp_split_to_table(s.text, '(?<=[.?!])\s+|\n+') as st(sentence)
             cross join lateral regexp_matches(coalesce(substring(btrim(st.sentence) from '^\S+\s+(.*)$'),''), '((?:1[89]|20)\d\d|[A-Z][a-z]+)', 'g') mk
             where st.sentence ~* '^\W*no\M' and mk[1] <> 'I'
               and lower(coalesce(pc.before,'')) !~ ('(^|[^a-z0-9''])' || lower(mk[1]) || '($|[^a-z0-9''])'))
"""


def final(sql: str) -> str:
    """The panel's own select: from the last `select` outside every bracket,
    so the shared tables it opens with are left out. Brackets inside a quoted
    literal do not count; an escaped quote ('') closes and reopens it."""
    depth, at, quoted = 0, 0, False
    for i, ch in enumerate(sql):
        if ch == "'":
            quoted = not quoted
        if quoted:
            continue
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if (
            depth == 0
            and SELECT.match(sql, i)
            and (i == 0 or not WORD.match(sql[i - 1]))
        ):
            at = i
    return sql[at:]


def by_version(sql: str) -> bool:
    """Whether the panel's own select groups by prompt version."""
    return bool(re.search(r"group by[^;]*prompt_version", final(sql), re.S | re.I))


def fragments(tail: str) -> str:
    """A query over the shared tables: `tail` is the final select."""
    return f"with recursive {FRAGMENTS.strip()}\n{tail}"


# The dataset. Every time is a whole number of days before today, so the
# 28-day silence and the 7-day return read the same on any day the gate runs.

ANN, BO, CY, TEST = "ann@example.com", "bo@example.com", "cy@example.com", "claude-test"


def add(of: ItemKind, iid, **fields) -> dict:
    return {"item_kind": of.value, "item_id": iid, "field": None, "before": None,
            "after": {"id": iid, **fields}}  # fmt: skip


def put(of: ItemKind, iid, field: str, after, before=None) -> dict:
    return {"item_kind": of.value, "item_id": iid, "field": field, "before": before,
            "after": after}  # fmt: skip


def drop(of: ItemKind, iid, before: dict) -> dict:
    return {"item_kind": of.value, "item_id": iid, "field": None, "before": before,
            "after": None}  # fmt: skip


def _row(table, **columns):
    row = table(**columns)
    db.session.add(row)
    db.session.flush()
    return row


class Sitting:
    """One chat discussion: each turn is the person's message, the coach's
    reply, its tool calls, its change rows and its done row."""

    def __init__(
        self, user: User, diagram: Diagram, at: datetime.datetime, version="v1"
    ):
        self.user, self.diagram, self.at, self.version = user, diagram, at, version
        self.discussion = _row(
            Discussion, user_id=user.id, diagram_id=diagram.id, synthetic=False,
            title_set_by_user=False, created_at=at,
        )  # fmt: skip
        self.person = _row(
            Speaker, discussion_id=self.discussion.id, type=SpeakerType.Subject
        )
        self.coach = _row(
            Speaker, discussion_id=self.discussion.id, type=SpeakerType.Expert
        )
        self.order = 0
        self.turns: list[str] = []

    def tick(self) -> datetime.datetime:
        self.at += datetime.timedelta(minutes=1)
        return self.at

    def say(
        self, speaker: Speaker, text: str, turn_id: str | None, version=None
    ) -> Statement:
        self.order += 1
        return _row(
            Statement, discussion_id=self.discussion.id, speaker_id=speaker.id, text=text,
            kind=StatementKind.Turn, order=self.order, turn_id=turn_id,
            prompt_version=version, created_at=self.tick(),
        )  # fmt: skip

    def turn(self, said: str, reply: str, calls=(), writes=(), coverage=None) -> str:
        """`calls` are (tool, args, refusal); `writes` are lists of deltas, one
        change row each."""
        turn_id = f"{self.discussion.id}-{len(self.turns) + 1}"
        self.turns.append(turn_id)
        asked = self.say(self.person, said, turn_id)
        seq = 0
        for tool, args, refusal in calls:
            seq += 1
            _row(
                TurnEvent, turn_id=turn_id, discussion_id=self.discussion.id, seq=seq,
                kind="tool_call", created_at=self.tick(),
                payload={"type": "tool_call", "name": tool, "args": args, "refusal": refusal},
            )  # fmt: skip
        for deltas in writes:
            change(self.diagram, Author.Coach, turn_id, self.tick(), deltas, asked.id)
        answer = self.say(self.coach, reply, turn_id, self.version)
        done = {"type": "done", "statement_id": answer.id}
        if coverage:
            done["coverage"] = {"before": coverage, "after": coverage}
        _row(
            TurnEvent, turn_id=turn_id, discussion_id=self.discussion.id, seq=seq + 1,
            kind="done", payload=done, created_at=self.tick(),
        )  # fmt: skip
        return turn_id


def change(
    diagram, author: Author, turn_id: str, at, deltas: list[dict], statement_id=None
):
    return _row(
        Change, diagram_id=diagram.id, statement_id=statement_id, turn_id=turn_id,
        user_id=diagram.user_id, author=author, deltas=deltas, created_at=at,
    )  # fmt: skip


def coverage(required, known, asked, said_unknown, declined, not_asked) -> dict:
    return {"required": required, "known": known, "asked": asked,
            "said_unknown": said_unknown, "declined": declined, "not_asked": not_asked}  # fmt: skip


def build(today: datetime.datetime) -> dict:
    """Two real users with records (Ann's stored as JSON, Bo's pickled), one
    who left (Cy), the claude-test account and a scratch record, whose rows
    every query must leave out. Returns the turn ids by name."""

    def day(n: int, hour=10) -> datetime.datetime:
        return today.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=n, hours=-hour)

    def user(name: str, active=True, created=90) -> User:
        return _row(
            User, username=name, status="confirmed", active=active,
            timezone="America/Anchorage", created_at=day(created),
        )  # fmt: skip

    def diagram(owner: User, data: bytes, scratch=False) -> Diagram:
        return _row(
            Diagram,
            user_id=owner.id,
            data=data,
            scratch=scratch,
            created_at=owner.created_at,
        )

    as_json = json.dumps({"people": [], "events": []}).encode()
    ann, bo, cy, test = (
        user(ANN, created=61),
        user(BO, created=4),
        user(CY, False, 21),
        user(TEST),
    )
    da, db_ = diagram(ann, as_json), diagram(
        bo, pickle.dumps({"people": [], "events": []})
    )
    dy, dt, scratch = (
        diagram(cy, as_json),
        diagram(test, as_json),
        diagram(ann, as_json, True),
    )

    for email, used in (
        (ANN, day(61, 9)),
        (BO, day(4, 9)),
        (CY, day(21, 9)),
        ("dee@example.com", None),
        ("claude-test+1@example.com", day(5)),
    ):
        _row(Invitation, email=email, token=email, expires_at=day(-30), used_at=used,
             created_at=day(62))  # fmt: skip

    P, E, B, Q = ItemKind.Person, ItemKind.Event, ItemKind.PairBond, ItemKind.Question
    ids = {}

    # Ann, sitting 1: parents, their marriage and divorce, a fact question on
    # her mother's health that she cannot answer.
    s1 = Sitting(ann, da, day(60), "v1")
    ids["t1"] = s1.turn(
        "My mother Mary and my father Tom divorced in 1990.",
        "I'm sorry to hear that. When did Mary and Tom marry?",
        calls=[("edit_person", {"name": "Mary"}, None), ("edit_person", {"name": "Tom"}, None),
               ("edit_pair_bond", {"person_a": 2, "person_b": 3}, None),
               ("edit_person", {"id": 1, "parents": 1}, None),
               ("edit_event", {"kind": "divorced"}, None)],
        writes=[[add(P, 2, name="Mary", gender="female")], [add(P, 3, name="Tom", gender="male")],
                [add(B, 1, person_a=2, person_b=3)], [put(P, 1, "parents", 1)],
                [add(E, 1, kind="divorced", person=2, spouse=3, dateTime="1990-01-01")]],
    )  # fmt: skip
    ids["t2"] = s1.turn(
        "They married in 1980.",
        "Thank you. How was Mary's health over the years?",
        calls=[("edit_event", {"kind": "married"}, None),
               ("add_question", {"kind": "fact", "fact": "health", "item_kind": "person",
                                 "item_id": 2, "state": "asked"}, None)],
        writes=[[add(E, 2, kind="married", person=2, spouse=3, dateTime="1980-06-01")],
                [add(Q, "q1", kind="fact", fact="health", item_kind="person", item_id="2",
                     state="asked", text="How was Mary's health?")]],
    )  # fmt: skip
    ids["t3"] = s1.turn(
        "I don't know.",
        "That's fine. Did Tom have brothers or sisters?",
        calls=[("set_question", {"id": "q1", "outcome": "unknown"}, None)],
        writes=[[put(Q, "q1", "outcome", "unknown")], [put(Q, "q1", "state", "resolved", "asked")]],
    )  # fmt: skip

    # Ann, sitting 2, two days later: her mother's death, a guess that does
    # not fit, a brother the coach made up and she removes, a date she fixes,
    # two objections.
    s2 = Sitting(ann, da, day(58), "v2")
    ids["t4"] = s2.turn(
        "Mary died in 2015 of cancer.",
        "I'm sorry. How did the family take [[event:3|Mary's death]]?",
        calls=[("edit_event", {"kind": "death"}, None)],
        writes=[[add(E, 3, kind="death", person=2, dateTime="2015-03-01")]],
    )  # fmt: skip
    ids["t5"] = s2.turn(
        "We stopped talking after that.",
        "It sounds like there was distance between you and Tom after Mary died.",
        calls=[("add_impression", {"text": "distance after the death"}, None),
               ("edit_event", {"kind": "shift"}, "no such person"),
               ("edit_event", {"kind": "shift"}, None), ("edit_person", {"name": "Sam"}, None)],
        writes=[[add(Q, "q2", kind="impression", state="raised", text="Distance after the death")],
                [add(E, 4, kind="shift", person=1, relationship="distance",
                     relationshipTargets=[3], dateTime="2015-06-01")],
                [add(P, 4, name="Sam", gender="male", parents=1)]],
    )  # fmt: skip
    tap = s2.tick()
    _row(ProductEvent, user_id=ann.id, session_id="web-ann", diagram_id=da.id, screen="chat",
         name="impression_partly", item_kind="question", item_id="q2", client_at=tap)  # fmt: skip
    tap = s2.tick()
    change(da, Author.User, "hand-1", tap, [put(Q, "q2", "outcome", "doesnt_fit")])
    change(
        da, Author.User, "hand-2", tap, [put(Q, "q2", "state", "resolved", "raised")]
    )
    _row(Interaction, diagram_id=da.id, user_id=ann.id, kind=InteractionKind.DoesntFit,
         item_kind=ItemKind.Question, item_id="q2", created_at=tap)  # fmt: skip
    _row(ProductEvent, user_id=ann.id, session_id="web-ann", diagram_id=da.id, screen="chat",
         name="impression_doesnt_fit", item_kind="question", item_id="q2", client_at=tap)  # fmt: skip
    sam = {"id": 4, "name": "Sam", "gender": "male", "parents": 1}
    change(da, Author.User, "hand-3", s2.tick(), [drop(P, 4, sam)])
    change(
        da,
        Author.User,
        "hand-4",
        s2.tick(),
        [put(E, 2, "dateTime", "1981-06-01", "1980-06-01")],
    )
    ids["t6"] = s2.turn(
        "That doesn't fit: [[impression:q2]]", "Thanks. What was it like instead?"
    )
    ids["t7"] = s2.turn(
        "No, Tom moved to Denver in 2016.",
        "Did that move change how often you spoke?",
        calls=[("edit_event", {"kind": "noted"}, None)],
        writes=[[add(E, 5, kind="noted", item="places", person=3, dateTime="2016-01-01",
                     description="moved to Denver")]],
    )  # fmt: skip
    ids["t8"] = s2.turn("I already told you, we barely spoke.", "I understand.")
    _row(Report, kind=ReportKind.Bug, status=ReportStatus.Sent, user_id=ann.id,
         diagram_id=da.id, turn_id=ids["t8"], release="test", created_at=s2.tick())  # fmt: skip

    # Ann, sitting 3, 23 days later and her last: her father's second wife, a
    # question on how they met that she dismisses, then a failed turn.
    s3 = Sitting(ann, da, day(35), "v2")
    ids["t9"] = s3.turn(
        "My father Tom remarried in 2018 to Joan.",
        "When did Tom and Joan meet?",
        calls=[("edit_person", {"name": "Joan"}, None),
               ("edit_pair_bond", {"person_a": 3, "person_b": 5}, None),
               ("edit_event", {"kind": "married"}, None),
               ("add_question", {"kind": "fact", "fact": "met", "item_kind": "pair_bond",
                                 "item_id": 2, "state": "asked"}, None)],
        writes=[[add(P, 5, name="Joan", gender="female")], [add(B, 2, person_a=3, person_b=5)],
                [add(E, 6, kind="married", person=3, spouse=5, dateTime="2018-05-01")],
                [add(Q, "q3", kind="fact", fact="met", item_kind="pair_bond", item_id="2",
                     state="asked", text="When did they meet?")],
                [add(ItemKind.Cluster, "c1", title="After the divorce", eventIds=[1, 2, 3])]],
    )  # fmt: skip
    tap = s3.tick()
    change(
        da, Author.User, "hand-5", tap, [put(Q, "q3", "outcome", "declined_by_user")]
    )
    _row(Interaction, diagram_id=da.id, user_id=ann.id, kind=InteractionKind.Dismiss,
         item_kind=ItemKind.Question, item_id="q3", created_at=tap)  # fmt: skip
    _row(ProductEvent, user_id=ann.id, session_id="web-ann", diagram_id=da.id, screen="chat",
         name="question_dismiss", item_kind="question", item_id="q3", client_at=tap)  # fmt: skip
    ids["t10"] = s3.turn(
        "I'm not sure.",
        "Sorry, something went wrong on my side.",
        coverage=coverage(10, 4, 1, 1, 0, 4),
    )
    for turn_id, kind in (
        (ids["t5"], ObservationKind.ToolRefused),
        (ids["t9"], ObservationKind.DuplicatePerson),
        (ids["t10"], ObservationKind.TurnFailed),
    ):
        _row(Observation, diagram_id=da.id, turn_id=turn_id, kind=kind, detail={},
             created_at=s3.at)  # fmt: skip
    for turn_id, fallback in (
        (ids["t9"], {"from": "claude-opus-5-5"}),
        (ids["t10"], None),
    ):
        _row(ModelCall, user_id=ann.id, diagram_id=da.id, turn_id=turn_id, purpose=Purpose.Coach,
             model="claude-opus-4-6", fallback=fallback, input_tokens=1000, output_tokens=100,
             cache_creation_tokens=0, cache_read_tokens=0, cost_usd=0.01, duration_ms=1000,
             tool_calls=1, created_at=s3.at)  # fmt: skip

    # Bo, pickled record, one sitting three days ago: his grandmother's death,
    # then he opens the picture, looks at her and talks about her.
    sb = Sitting(bo, db_, day(3), "v2")
    ids["tb1"] = sb.turn(
        "My grandmother Rose died in 1999.",
        "How old was Rose then?",
        calls=[("edit_person", {"name": "Rose"}, None), ("edit_event", {"kind": "death"}, None)],
        writes=[[add(P, 2, name="Rose", gender="female")],
                [add(E, 1, kind="death", person=2, dateTime="1999-01-01")]],
    )  # fmt: skip
    look = sb.tick()
    _row(ProductEvent, user_id=bo.id, session_id="web-bo", diagram_id=db_.id, screen="chat",
         name="picture_up", client_at=look)  # fmt: skip
    _row(ProductEvent, user_id=bo.id, session_id="web-bo", diagram_id=db_.id, screen="chat",
         name="person_open", item_kind="person", item_id="2", client_at=look)  # fmt: skip
    _row(Interaction, diagram_id=db_.id, user_id=bo.id, kind=InteractionKind.Look,
         item_kind=ItemKind.Person, item_id="2", created_at=look)  # fmt: skip
    ids["tb2"] = sb.turn(
        "Rose was strict.",
        "What was she strict about?",
        calls=[("edit_event", {"kind": "shift"}, None)],
        writes=[[add(E, 2, kind="shift", person=2, functioning="up", dateTime="1990-01-01")]],
        coverage=coverage(4, 2, 0, 0, 1, 1),
    )  # fmt: skip

    # Cy: one sitting, nothing written, then left.
    ids["ty1"] = Sitting(cy, dy, day(20), "v2").turn(
        "Hello.", "Hi, what brings you here?"
    )

    # Rows no query may count: the claude-test account and a scratch record.
    for owner, record in ((test, dt), (ann, scratch)):
        other = Sitting(owner, record, day(2), "v2")
        noise = other.turn(
            "That's not right, I already told you about Mary.",
            "Sorry, who is Mary?",
            calls=[("edit_person", {"name": "Mary"}, "no")],
            writes=[[add(P, 9, name="Mary", gender="female")]],
            coverage=coverage(5, 5, 0, 0, 0, 0),
        )
        _row(Observation, diagram_id=record.id, turn_id=noise, kind=ObservationKind.TurnFailed,
             detail={}, created_at=other.at)  # fmt: skip
        _row(ProductEvent, user_id=owner.id, session_id="web-x", diagram_id=record.id,
             screen="chat", name="picture_up", client_at=other.at)  # fmt: skip
    db.session.commit()
    return ids
