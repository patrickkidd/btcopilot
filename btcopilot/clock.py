"""The person's day, not the server's [Oracle: R-0758].

The server keeps UTC and every stored time stays naive UTC. The page sends the
browser's IANA zone with each message, and the coach's "today", the follow-up
date check and the day a question was asked on are worked out in it; otherwise
an evening in Alaska is already tomorrow to the coach. With no zone (a resumed
turn, a scheduled job, a name the server does not know) the day is the
server's own, as it always was: UTC on the box.
"""

import datetime
import zoneinfo

UTC = datetime.timezone.utc


def zone(name: object) -> str | None:
    """The zone name as sent, when it is one the server knows; else None."""
    if not isinstance(name, str) or not name:
        return None
    try:
        zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return name


def day(at: datetime.datetime, zone_name: str | None = None) -> datetime.date:
    """The calendar day a stored (naive UTC) moment fell on where the person
    is; with no zone, the day it was stored under."""
    if zone_name is None:
        return at.date()
    return at.replace(tzinfo=UTC).astimezone(zoneinfo.ZoneInfo(zone_name)).date()


def today(zone_name: str | None = None) -> datetime.date:
    """The calendar day where the person is; with no zone, the server's own."""
    if zone_name is None:
        return datetime.date.today()
    return day(datetime.datetime.utcnow(), zone_name)
