"""Where a running turn's events live while it runs.

The turn runs in the worker and the page reads it from the web container, so
the events go through Redis: one list per turn, replayable from any point, and
one channel per turn to follow it live. The discussion remembers the turn it
is running, which is how a page that comes back knows to reattach.
"""

import enum
import json
import queue
import threading
import time

import redis
from flask import current_app

TTL = 3600
TICK = 1.0
# How long a session stays held for the turn it is running. A worker that dies
# mid-turn says nothing, so the hold has to run out on its own — in minutes, not
# in an hour. The task pushes it out again with every event it writes, so a turn
# that is still working never lets go.
RUNNING_TTL = 180


class TurnLogBackend(enum.StrEnum):
    """Which store `store()` builds. An explicit config choice, not a fallback."""

    Memory = "memory"
    Redis = "redis"


class TurnEventKind(enum.StrEnum):
    """Everything the page can be told while a turn runs."""

    ToolCall = "tool_call"
    RecordPatch = "record_patch"
    View = "view"
    Text = "text"
    TextReset = "text_reset"
    # What the grouping of the record's events now says that it did not before,
    # one sentence each. The coach says it in its own words; the page shows
    # nothing for it.
    Story = "story"
    Done = "done"
    Failed = "failed"
    # Every model declined the message on safety grounds. The page says so in
    # the coach's voice and offers no retry, since the same words would be
    # declined again [Oracle: R-0410].
    Refused = "refused"


ENDS = (
    TurnEventKind.Done.value,
    TurnEventKind.Failed.value,
    TurnEventKind.Refused.value,
)


def ended(event: dict) -> bool:
    return event["type"] in ENDS


class RedisLog:
    """The one that runs in the box."""

    def __init__(self, url: str):
        self.redis = redis.Redis.from_url(url)

    def append(self, turn_id: str, event: dict) -> int:
        key = f"turn:{turn_id}"
        pipe = self.redis.pipeline()
        pipe.rpush(key, json.dumps(event))
        pipe.expire(key, TTL)
        seq = pipe.execute()[0]
        self.redis.publish(key, json.dumps({"seq": seq, "event": event}))
        return seq

    def read_from(self, turn_id: str, last_id: int) -> list[tuple[int, dict]]:
        raw = self.redis.lrange(f"turn:{turn_id}", last_id, -1)
        return [(last_id + i + 1, json.loads(one)) for i, one in enumerate(raw)]

    def subscribe(self, turn_id: str):
        """Every event published from here on, and None each tick so the reader
        can send its heartbeat. Listening starts here, not on the first read,
        so nothing published while the reader catches up is missed."""
        sub = self.redis.pubsub(ignore_subscribe_messages=True)
        sub.subscribe(f"turn:{turn_id}")

        def following():
            try:
                while True:
                    message = sub.get_message(timeout=TICK)
                    if message is None:
                        yield None
                        continue
                    carried = json.loads(message["data"])
                    yield carried["seq"], carried["event"]
            finally:
                sub.close()

        return following()

    def running(self, discussion_id: int) -> str | None:
        found = self.redis.get(f"discussion:{discussion_id}:turn")
        return found.decode() if found else None

    def owner(self, turn_id: str) -> int | None:
        """Which session a turn belongs to, kept for as long as the turn can be
        replayed, so a finished turn is still only its owner's to read."""
        found = self.redis.get(f"turn:{turn_id}:session")
        return int(found) if found else None

    def start(self, discussion_id: int, turn_id: str) -> bool:
        if not self.redis.set(
            f"discussion:{discussion_id}:turn", turn_id, nx=True, ex=RUNNING_TTL
        ):
            return False
        self.redis.set(f"turn:{turn_id}:session", discussion_id, ex=TTL)
        return True

    def keep(self, discussion_id: int) -> None:
        self.redis.expire(f"discussion:{discussion_id}:turn", RUNNING_TTL)

    def clear(self, discussion_id: int) -> None:
        self.redis.delete(f"discussion:{discussion_id}:turn")


class MemoryLog:
    """The same log in one process, which is what the tests read and write."""

    def __init__(self):
        self.events: dict[str, list[dict]] = {}
        self.turns: dict[int, tuple[str, float]] = {}
        self.owners: dict[str, int] = {}
        self.readers: dict[str, list[queue.Queue]] = {}
        self.lock = threading.Lock()

    def append(self, turn_id: str, event: dict) -> int:
        with self.lock:
            kept = self.events.setdefault(turn_id, [])
            kept.append(event)
            seq = len(kept)
            for reader in self.readers.get(turn_id, []):
                reader.put((seq, event))
        return seq

    def read_from(self, turn_id: str, last_id: int) -> list[tuple[int, dict]]:
        with self.lock:
            kept = self.events.get(turn_id, [])[last_id:]
        return [(last_id + i + 1, one) for i, one in enumerate(kept)]

    def subscribe(self, turn_id: str):
        reader: queue.Queue = queue.Queue()
        with self.lock:
            self.readers.setdefault(turn_id, []).append(reader)

        def following():
            try:
                while True:
                    try:
                        yield reader.get(timeout=TICK)
                    except queue.Empty:
                        yield None
            finally:
                with self.lock:
                    self.readers[turn_id].remove(reader)

        return following()

    def running(self, discussion_id: int) -> str | None:
        held = self.turns.get(discussion_id)
        if held is None:
            return None
        turn_id, until = held
        if until > time.time():
            return turn_id
        self.clear(discussion_id)
        return None

    def owner(self, turn_id: str) -> int | None:
        return self.owners.get(turn_id)

    def start(self, discussion_id: int, turn_id: str) -> bool:
        with self.lock:
            if self.running(discussion_id) is not None:
                return False
            self.turns[discussion_id] = (turn_id, time.time() + RUNNING_TTL)
            self.owners[turn_id] = discussion_id
        return True

    def keep(self, discussion_id: int) -> None:
        held = self.turns.get(discussion_id)
        if held:
            self.turns[discussion_id] = (held[0], time.time() + RUNNING_TTL)

    def clear(self, discussion_id: int) -> None:
        self.turns.pop(discussion_id, None)


_store = None


def use(store) -> None:
    """The tests put their own log in; nothing else calls this."""
    global _store
    _store = store


def store():
    global _store
    if _store is None:
        backend = current_app.config["TURN_LOG"]
        if backend == TurnLogBackend.Memory:
            _store = MemoryLog()
        else:
            _store = RedisLog(current_app.config["CELERY_BROKER_URL"])
    return _store


def append(turn_id: str, event: dict) -> int:
    return store().append(turn_id, event)


def read_from(turn_id: str, last_id: int) -> list[tuple[int, dict]]:
    return store().read_from(turn_id, last_id)


def subscribe(turn_id: str):
    return store().subscribe(turn_id)


def running(discussion_id: int) -> str | None:
    return store().running(discussion_id)


def owner(turn_id: str) -> int | None:
    return store().owner(turn_id)


def start(discussion_id: int, turn_id: str) -> bool:
    return store().start(discussion_id, turn_id)


def keep(discussion_id: int) -> None:
    store().keep(discussion_id)


def clear(discussion_id: int) -> None:
    store().clear(discussion_id)
