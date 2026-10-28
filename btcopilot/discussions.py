"""Discussion lifecycle shared by every surface that starts or continues a
session."""

import datetime

from sqlalchemy import func

from btcopilot import auth, diagramjson, profile, record
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.models.diagram import owner_row
from btcopilot.models import (
    Author,
    Discussion,
    DiscussionKind,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
)
from btcopilot import turnlog
from btcopilot.schema import DEFAULT_SUBJECT_NAME

PREVIEW_CHARS = 120
# Nobody opens or closes a sitting by hand. Words
# that come after the family has been quiet this long start the next sitting.
SITTING_GAP = datetime.timedelta(hours=12)


def utc_iso(when: datetime.datetime) -> str:
    """Stored times are naive UTC; the browser needs to be told so, or it reads
    them as its own local time."""
    return when.replace(tzinfo=datetime.timezone.utc).isoformat()


def last_activity(discussion: Discussion):
    times = [s.created_at for s in discussion.statements if s.created_at]
    return max(times) if times else discussion.created_at


def clip(said: str | None) -> str | None:
    if said is None:
        return None
    words = " ".join(said.split())
    return (
        words if len(words) <= PREVIEW_CHARS else words[:PREVIEW_CHARS].rstrip() + "…"
    )


def preview(discussion: Discussion) -> str | None:
    """The first thing the client said, the way a notes or messages list
    previews its content under the title."""
    return clip(
        next(
            (
                s.text
                for s in discussion.statements
                if s.text and s.speaker_id != discussion.chat_ai_speaker_id
            ),
            None,
        )
    )


def row(
    discussion: Discussion, last: datetime.datetime, count: int, first: str | None
) -> dict:
    """`turn` is the turn the coach is running on this session, so a page that
    has just loaded, or come back to the front, knows to attach to it."""
    return {
        "id": discussion.id,
        "diagram_id": discussion.diagram_id,
        "title": discussion.title,
        "summary": discussion.summary,
        "preview": first,
        "title_set_by_user": discussion.title_set_by_user,
        "last_activity": utc_iso(last),
        "message_count": count,
        "kind": DiscussionKind(discussion.kind).value,
        "turn": turnlog.running(discussion.id),
        "date": (
            discussion.discussion_date.isoformat()
            if discussion.discussion_date
            else None
        ),
    }


def session_payload(discussion: Discussion) -> dict:
    return row(
        discussion,
        last_activity(discussion),
        len(discussion.statements),
        preview(discussion),
    )


def listed(found) -> list[dict]:
    """The rows of the sessions `found` picks, most recently active first. The
    database counts and dates each one and hands back only its first line,
    never every line of every session."""
    ids = Statement.discussion_id.in_(found.with_entities(Discussion.id))
    stats = (
        db.session.query(
            Statement.discussion_id,
            func.count(Statement.id).label("count"),
            func.max(Statement.created_at).label("last"),
        )
        .filter(ids)
        .group_by(Statement.discussion_id)
        .subquery()
    )
    told = (
        db.session.query(
            Statement.discussion_id,
            Statement.text,
            func.row_number()
            .over(
                partition_by=Statement.discussion_id,
                order_by=(Statement.order, Statement.id),
            )
            .label("at"),
        )
        .join(Discussion)
        .filter(
            ids,
            Statement.text.isnot(None),
            Statement.text != "",
            Statement.speaker_id.is_distinct_from(Discussion.chat_ai_speaker_id),
        )
        .subquery()
    )
    last = func.coalesce(stats.c.last, Discussion.created_at)
    rows = (
        found.outerjoin(stats, stats.c.discussion_id == Discussion.id)
        .outerjoin(told, (told.c.discussion_id == Discussion.id) & (told.c.at == 1))
        .add_columns(last, stats.c.count, told.c.text)
        .order_by(last.desc(), Discussion.id.desc())
    )
    return [row(d, at, count or 0, clip(text)) for d, at, count, text in rows]


def all_sessions():
    """Every session on every family. A discussion missing either chat speaker
    id is not one: its speakers are not the two chat roles, so every line would
    render as the user's."""
    return Discussion.query.filter(
        Discussion.chat_user_speaker_id.isnot(None),
        Discussion.chat_ai_speaker_id.isnot(None),
    )


def real_sessions():
    """Every session on every family that is not a throwaway copy (the replay
    and shadow families are marked scratch) or deleted by its owner."""
    return (
        all_sessions()
        .join(Diagram)
        .filter(Diagram.scratch.is_(False), Diagram.deleted_at.is_(None))
    )


def chats(user, diagram_id: int):
    """The user's sessions on one family."""
    return all_sessions().filter_by(user_id=user.id, diagram_id=diagram_id)


def newest(found) -> list[Discussion]:
    """Most recently active first."""
    return sorted(found, key=lambda d: (last_activity(d), d.id), reverse=True)


def previous(discussion: Discussion) -> Discussion | None:
    """The sitting spoken in before this one, on the same family."""
    earlier = [
        d
        for d in chats(discussion.user, discussion.diagram_id)
        if d.id != discussion.id and d.statements
    ]
    return newest(earlier)[0] if earlier else None


def family(user, diagram: Diagram | None) -> Diagram:
    """A caller that knows which diagram the session belongs on says so; the
    personal app's own routes do not, and get the free one, made on first use."""
    diagram = diagram or user.free_diagram
    if diagram is None:
        # written as set_free_diagram writes it: their own family
        diagram = Diagram(
            user_id=user.id,
            name=f"{user.username} Personal Case File",
            data=diagramjson.dumps({}),
            access_rights=[owner_row(user.id, profile.FIRST_PERSON_ID)],
        )
        db.session.add(diagram)
        db.session.flush()
        user.free_diagram_id = diagram.id
    return diagram


def create_discussion(data: dict, diagram: Diagram | None = None) -> Discussion:
    user = auth.current_user()
    discussion = open_session(user, family(user, diagram))
    db.session.commit()
    return discussion


def sitting(user, diagram: Diagram) -> Discussion:
    """The sitting the next words on this family go into, from either speaker:
    the one last spoken in, until the family has been quiet for SITTING_GAP;
    then a new one, which the coach opens with nothing. One nobody has spoken
    in yet, such as a note just made, is still waiting for its first words.
    Flushed, not committed: the words that start it commit it."""
    last = max(chats(user, diagram.id), key=lambda d: (last_activity(d), d.id), default=None)
    if last and (
        not last.statements
        or datetime.datetime.utcnow() - last_activity(last) <= SITTING_GAP
    ):
        return last
    return open_session(user, diagram)


def coach_said(discussion: Discussion, text: str, **more) -> Statement:
    """The coach's words written straight into the session with no model
    turn: a message it writes first, or an import's report [Oracle: R-0947]."""
    statement = Statement(
        discussion_id=discussion.id,
        text=text,
        speaker=discussion.chat_ai_speaker,
        order=discussion.next_order(),
        kind=StatementKind.Turn,
        **more,
    )
    db.session.add(statement)
    return statement


def voice(user, diagram: Diagram, data) -> tuple[int | None, str]:
    """The person the user speaks as on the case and the label they speak
    under: the family's subject by the subject's label, a member of the family
    by their name, and a human coach, who is no one in it, by their own."""
    person_id = profile.person_of(user, diagram)
    if person_id is None:
        return None, user.full_name().strip() or user.username
    if profile.is_subject(person_id, data):
        return person_id, data.subject_display_name()
    named = next((p for p in data.people if p.get("id") == person_id), {})
    return person_id, named.get("name") or DEFAULT_SUBJECT_NAME


def open_session(user, diagram: Diagram) -> Discussion:
    """A session on the diagram with its two chat speakers: the user as who
    they are on the case, and the coach."""
    # Read the speaker label off the diagram directly (not the lazily-populated
    # relationship) so a named primary is honored even at create time.
    person_id, name = voice(user, diagram, diagram.get_diagram_data())

    discussion = Discussion(
        user_id=user.id,
        diagram_id=diagram.id,
        speakers=[
            Speaker(name=name, type=SpeakerType.Subject, person_id=person_id),
            # The coach is not in the family, so it points at no person.
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(discussion)
    db.session.flush()
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    discussion.chat_ai_speaker_id = discussion.speakers[1].id
    return discussion


def sync_chat_speakers(discussion: Discussion):
    """Ensure the person the family belongs to exists in the diagram, and sync
    the Subject speaker to who the user is on the case: keep person_id and the
    display label (real name, else neutral default) in step so the chat
    transcript and extraction prompt name the user, not "Client". A human
    coach on the case speaks as no one in it."""
    if not discussion.diagram:
        return
    diagram = discussion.diagram
    diagram_data = diagram.get_diagram_data()
    own = profile.person_of(diagram.user, diagram) is not None
    user_person_id, changed = diagram_data.ensure_chat_defaults(
        profile.PLACEHOLDER_NAME if own else None
    )
    if changed:
        before = diagramjson.loads(diagram.data)
        diagram.set_diagram_data(diagram_data)
        record.told_on_commit(
            diagram.id,
            record.diff(before, diagramjson.loads(diagram.data)),
            None,
            Author.User,
            diagram.version,
        )
    person_id, name = voice(discussion.user, diagram, diagram_data)

    user_speaker = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Subject
    ).first()
    if user_speaker:
        if user_speaker.person_id != person_id:
            user_speaker.person_id = person_id
        if user_speaker.name != name:
            user_speaker.name = name


def transcript_voices(utterances: list[dict]) -> list[dict]:
    """The voices a diarized transcript holds, each with the first thing it
    says — which is what the reader is shown when saying who is who."""
    found: dict[str, dict] = {}
    for utterance in utterances:
        label = utterance.get("speaker", "Unknown")
        if label not in found:
            found[label] = {"label": label, "said": utterance.get("text", "")}
    return list(found.values())


def transcript_statements(
    discussion: Discussion, utterances: list[dict], voices: dict[str, dict]
) -> dict[str, Speaker]:
    """Turn a diarized transcript into the discussion's speakers and
    statements. `voices` says what each voice label is; a label the caller did
    not name is a subject called by its own label."""
    speakers: dict[str, Speaker] = {}
    for order, utterance in enumerate(utterances):
        label = utterance.get("speaker", "Unknown")
        if label not in speakers:
            said = voices.get(label, {})
            speaker = Speaker(
                discussion_id=discussion.id,
                name=said.get("name") or label,
                type=SpeakerType(said.get("type", SpeakerType.Subject)),
                person_id=said.get("person_id"),
            )
            db.session.add(speaker)
            db.session.flush()
            speakers[label] = speaker
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=speakers[label].id,
                text=utterance.get("text", ""),
                order=order,
            )
        )
    return speakers


def create_recording(
    diagram: Diagram,
    utterances: list[dict],
    voices: dict[str, dict],
    title: str,
    date: datetime.date | None,
) -> Discussion:
    """A recorded session read into the record as a conversation like any other
    (R-0267). The clinician's voice becomes the coach's side of the thread, so
    the thread reads the way a chat session does and can be coded."""
    discussion = Discussion(
        user_id=auth.current_user().id,
        diagram_id=diagram.id,
        title=title,
        title_set_by_user=True,
        kind=DiscussionKind.Recording,
        discussion_date=date,
    )
    db.session.add(discussion)
    db.session.flush()
    speakers = transcript_statements(discussion, utterances, voices)
    expert = next((s for s in speakers.values() if s.type == SpeakerType.Expert), None)
    subject = next(
        (s for s in speakers.values() if s.type == SpeakerType.Subject), None
    )
    if expert is None or subject is None:
        raise ValueError("A recording needs one clinician voice and one client voice")
    discussion.chat_ai_speaker_id = expert.id
    discussion.chat_user_speaker_id = subject.id
    db.session.commit()
    return discussion
