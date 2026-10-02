"""Every view and object in the app has an address under /app/ (R-0055). The
table lives in web/src/place.ts; this mirrors it and a test keeps the two
equal. The server reads an address to serve the page at it, to take a notice's
link, and to check where the coach's navigate call goes."""

import enum
import re

APP = "/app/"
UNDATED = "undated"


class Place(enum.StrEnum):
    Chat = ""
    Message = "chat/:n"
    Sessions = "sessions"
    Session = "sessions/:n"
    Account = "account"
    Profile = "account/profile"
    Notices = "account/notices"
    Notice = "account/notices/:n"
    Coach = "account/coach"
    Appearance = "account/appearance"
    Diagrams = "account/diagrams"
    Theirs = "account/diagrams/:n"
    Plan = "account/plan"
    Task = "account/coding-task"
    Agenda = "account/meeting"
    MeetingDay = "account/meeting/:day"
    MeetingCut = "account/meeting/:day/:n"
    Pairs = "account/better-replies"
    Literature = "account/literature-review"
    Cluster = "cluster/:key"
    NewEvent = "event/new"
    Event = "event/:n"
    EventEditor = "event/:n/edit"
    NewPerson = "person/new"
    Person = "person/:n"
    Events = "events"
    People = "people"
    Questions = "questions"
    Play = "play/:n"
    PlayStep = "play/:n/:n"
    Coding = "coding/:n"
    Vote = "vote/:n"
    Meeting = "meeting/:n"
    Result = "result/:n"
    Guidelines = "guidelines"


# The coder's and reviewer's screens: the coach offers and opens them only for
# a person with that role (R-0626).
CODER = frozenset(
    {
        Place.Task,
        Place.Agenda,
        Place.MeetingDay,
        Place.MeetingCut,
        Place.Literature,
        Place.Coding,
        Place.Vote,
        Place.Meeting,
        Place.Result,
        Place.Guidelines,
    }
)

SLOT = {
    ":n": re.compile(r"\d+"),
    ":key": re.compile(r"[\w.-]+"),
    ":day": re.compile(rf"\d{{4}}-\d{{2}}-\d{{2}}|{UNDATED}"),
}

# What the tool line calls each place, for those the record does not name.
WORDS = {
    Place.Chat: "the chat",
    Place.Message: "that message",
    Place.Sessions: "your sessions",
    Place.Session: "that session",
    Place.Account: "your account",
    Place.Profile: "your profile",
    Place.Notices: "your notices",
    Place.Notice: "that notice",
    Place.Coach: "the coach settings",
    Place.Appearance: "the appearance settings",
    Place.Diagrams: "your diagrams",
    Place.Theirs: "their diagrams",
    Place.Plan: "your plan",
    Place.Task: "your coding task",
    Place.Agenda: "the next meeting",
    Place.MeetingDay: "the meeting",
    Place.MeetingCut: "the meeting",
    Place.Pairs: "better replies",
    Place.Literature: "the Auditor's Coding Guide",
    Place.NewEvent: "a new event",
    Place.NewPerson: "a new person",
    Place.Events: "the events",
    Place.People: "the people",
    Place.Questions: "the questions",
    Place.Play: "the play-by-play",
    Place.PlayStep: "the play-by-play",
    Place.Coding: "the coding",
    Place.Vote: "the vote",
    Place.Meeting: "the meeting",
    Place.Result: "the meeting's result",
    Place.Guidelines: "the coding guidelines",
}


def parse(path: str) -> tuple[Place, list[str]] | None:
    """Which place an address names and what fills its slots, or None for one
    the app does not have. A trailing slash and anything after `?` or `#` are
    not part of it."""
    bare = re.split(r"[?#]", path)[0].rstrip("/")
    root = APP.rstrip("/")
    if bare != root and not bare.startswith(APP):
        return None
    words = [] if bare == root else bare[len(APP) :].split("/")
    for place in Place:
        want = place.value.split("/") if place.value else []
        if len(want) != len(words):
            continue
        if all(
            SLOT[part].fullmatch(word) if part in SLOT else part == word
            for part, word in zip(want, words)
        ):
            return place, [word for part, word in zip(want, words) if part in SLOT]
    return None
