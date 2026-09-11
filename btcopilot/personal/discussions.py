"""Discussion lifecycle shared by every surface that starts or continues a
session."""


from btcopilot import auth, diagramjson
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram
from btcopilot.personal.models import Discussion, Speaker, SpeakerType

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
