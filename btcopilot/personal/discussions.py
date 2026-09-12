"""Discussion lifecycle shared by every surface that starts or continues a
session."""


import datetime

from btcopilot import auth, diagramjson
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.personal.models import (
    Discussion,
    DiscussionKind,
    Speaker,
    SpeakerType,
    Statement,
)

def create_discussion(data: dict, diagram: Diagram | None = None) -> Discussion:
    """A caller that knows which diagram the session belongs on says so; the
    personal app's own routes do not, and get the free one."""
    user = auth.current_user()

    # Ensure user has a free_diagram
    diagram = diagram or user.free_diagram
    if diagram is None:
        diagram = Diagram(
            user_id=user.id,
            name=f"{user.username} Personal Case File",
            data=diagramjson.dumps({}),
        )
        db.session.add(diagram)
        db.session.flush()
        user.free_diagram_id = diagram.id

    # Read the speaker label off the diagram directly (not the lazily-populated
    # relationship) so a named primary is honored even at create time.
    subject_name = diagram.get_diagram_data().subject_display_name()

    discussion = Discussion(
        user_id=user.id,
        diagram_id=diagram.id,
        summary="New Discussion",
        speakers=[
            Speaker(name=subject_name, type=SpeakerType.Subject, person_id=1),
            # The coach is not in the family, so it points at no person.
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(discussion)
    db.session.flush()

    # Update discussion with speaker IDs for chat
    discussion.chat_user_speaker_id = discussion.speakers[0].id
    discussion.chat_ai_speaker_id = discussion.speakers[1].id

    db.session.commit()

    return discussion


def sync_chat_speakers(discussion: Discussion):
    """Ensure the person the user speaks as exists in the diagram, and sync the
    Subject speaker to the primary person: keep person_id and the display label
    (real name, else neutral default) in step so the chat transcript and
    extraction prompt name the user, not "Client"."""
    if not discussion.diagram:
        return
    diagram_data = discussion.diagram.get_diagram_data()
    user_person_id, changed = diagram_data.ensure_chat_defaults()
    if changed:
        discussion.diagram.set_diagram_data(diagram_data)

    user_speaker = Speaker.query.filter_by(
        discussion_id=discussion.id, type=SpeakerType.Subject
    ).first()
    if user_speaker:
        if user_speaker.person_id != user_person_id:
            user_speaker.person_id = user_person_id
        subject_name = diagram_data.subject_display_name()
        if user_speaker.name != subject_name:
            user_speaker.name = subject_name


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
