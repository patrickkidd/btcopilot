"""Which features people use: every screen opened and every named tap, per
person and page load, for Grafana to read straight from the table. The names
live in web/src/track.ts; these mirror them and a test keeps the two equal."""

import enum
from datetime import UTC, datetime

from btcopilot.extensions import db
from btcopilot.models import ProductEvent
from btcopilot.schema import ItemKind


class Screen(enum.StrEnum):
    Chat = "chat"
    Menu = "menu"
    Task = "task"
    Coding = "coding"
    Ballot = "ballot"
    Rules = "rules"
    Cut = "cut"
    Agenda = "agenda"
    Meeting = "meeting"
    Result = "result"


class Feature(enum.StrEnum):
    ScreenOpen = "screen_open"
    SendMessage = "send_message"
    ChipTap = "chip_tap"
    MessageLook = "message_look"
    Play = "play"
    TraceToChat = "trace_to_chat"
    PictureUp = "picture_up"
    PictureInfo = "picture_info"
    PictureClear = "picture_clear"
    OpenMenu = "open_menu"
    CloseMenu = "close_menu"
    TabEvents = "tab_events"
    TabPeople = "tab_people"
    TabQuestions = "tab_questions"
    QuestionChip = "question_chip"
    QuestionSession = "question_session"
    QuestionDismiss = "question_dismiss"
    ImpressionText = "impression_text"
    ImpressionEvidence = "impression_evidence"
    ImpressionSession = "impression_session"
    ImpressionDoesntFit = "impression_doesnt_fit"
    ImpressionPartly = "impression_partly"
    EventOpen = "event_open"
    PersonOpen = "person_open"
    PeopleOrder = "people_order"
    EventAdd = "event_add"
    PersonAdd = "person_add"
    EventSave = "event_save"
    EventDelete = "event_delete"
    PersonSave = "person_save"
    PersonDelete = "person_delete"
    ParentsSave = "parents_save"
    PairBondSave = "pair_bond_save"
    PairBondDelete = "pair_bond_delete"
    OpenSessions = "open_sessions"
    SessionOpen = "session_open"
    SessionNew = "session_new"
    SessionRename = "session_rename"
    SessionDelete = "session_delete"
    SessionToAgenda = "session_to_agenda"
    NoteNew = "note_new"
    UploadOpen = "upload_open"
    TaskOpen = "task_open"
    AgendaOpen = "agenda_open"
    OpenSettings = "open_settings"
    SettingChange = "setting_change"
    FamilySwitch = "family_switch"
    PasskeyAdd = "passkey_add"
    PasskeyRemove = "passkey_remove"
    SignOut = "sign_out"
    CodingDone = "coding_done"
    RulesOpen = "rules_open"
    Back = "back"
    BallotVote = "ballot_vote"
    BallotChange = "ballot_change"
    CutLine = "cut_line"
    CutConfirm = "cut_confirm"
    AgendaOpenItem = "agenda_open_item"
    AgendaAdd = "agenda_add"
    AgendaTakeOff = "agenda_take_off"
    AgendaNudge = "agenda_nudge"
    AgendaOpenVote = "agenda_open_vote"
    AgendaResult = "agenda_result"
    MeetingStart = "meeting_start"
    MeetingEnd = "meeting_end"
    MeetingKeep = "meeting_keep"
    MeetingChange = "meeting_change"
    MeetingUnresolved = "meeting_unresolved"


def record_events(user, session_id: str, events: list[dict]) -> int:
    rows = [
        ProductEvent(
            user_id=user.id,
            session_id=session_id,
            diagram_id=event.get("diagram_id"),
            screen=Screen(event["screen"]).value,
            name=Feature(event["name"]).value,
            item_kind=ItemKind(event["item_kind"]).value if event.get("item_kind") else None,
            item_id=event.get("item_id"),
            client_at=datetime.fromisoformat(event["at"])
            .astimezone(UTC)
            .replace(tzinfo=None),
        )
        for event in events
    ]
    db.session.add_all(rows)
    db.session.commit()
    return len(rows)
