import datetime

from btcopilot import proactive
from btcopilot.models import Notification, NotificationKind
from btcopilot.review import reminders

DAY = datetime.timedelta(days=1)


def sent() -> list[tuple[int, NotificationKind, int]]:
    return [
        (n.user_id, n.kind, n.cut_id)
        for n in Notification.query.order_by(Notification.id)
    ]


def test_a_dated_cut_tells_each_auditor_once_and_reminds_once(
    patrick, coder, session, turns
):
    # R-0055, R-0258, R-0265
    put = patrick.post(
        "/review/cuts",
        json={"end_statement_id": turns[1].id},
    )
    cut_id = put.json["id"]
    assert sent() == []

    meeting = datetime.datetime.now(proactive.ZONE).date() + 5 * DAY
    for day in (meeting + DAY, meeting):
        patrick.patch(f"/review/cuts/{cut_id}", json={"meeting_date": day.isoformat()})
    told = (coder.user.id, NotificationKind.Task, cut_id)
    assert sent() == [told]

    morning = datetime.datetime.combine(
        meeting - DAY, datetime.time(10), proactive.ZONE
    )
    now = morning.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    for hours in (0, 1):
        reminders.run(now=now + datetime.timedelta(hours=hours))
    assert sent() == [told, (coder.user.id, NotificationKind.Reminder, cut_id)]
