"""What the meeting produced, with nothing left to choose.

Derived and never stored, the way the agenda is: the counts, the two agreement
figures, how the coach's own pass scored, the guideline changes the AI wrote,
where it read the cut differently and what each coder tends to do. Readable by
anyone who took part, once the cut is ratified (R-0275).
"""

from flask import jsonify, request

from btcopilot.review import coachscore, snapshot, tendencies
from btcopilot.review.models import ReviewStatus, Rule
from btcopilot.review.routes import bp, coder, cut_or_404, human_codings
from btcopilot.review.routes.rules import payload as rule_payload


@bp.route("/result")
def result_read():
    coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if cut.ratified_at is None:
        raise ValueError("that cut is not ratified yet")
    # The room's own items: what only the coach wrote is read below as an
    # audit and is never counted as ratified or unresolved (R-0254).
    people = human_codings(cut)
    theirs = [
        item
        for item in cut.items
        if any(take.get("coding_id") in people for take in item.takes or [])
    ]
    counts = {status.value: 0 for status in ReviewStatus}
    for item in theirs:
        counts[item.status.value] += 1
    figures = cut.agreement or {}
    return jsonify(
        {
            "cut_id": cut.id,
            "ratified_at": cut.ratified_at.isoformat(),
            "items": len(theirs),
            "ratified": counts[ReviewStatus.Settled.value]
            + counts[ReviewStatus.Agreed.value],
            "unresolved": counts[ReviewStatus.Unresolved.value],
            "first_pass": figures.get(snapshot.AgreementPhase.FirstPass.value),
            "after": figures.get(snapshot.AgreementPhase.Ratified.value),
            "coach": coachscore.score(cut),
            "rules": [rule_payload(r) for r in _rules(cut)],
            "differed": cut.audit or [],
            "coders": tendencies.rows(cut),
        }
    )


def _rules(cut) -> list[Rule]:
    """The guidelines this meeting wrote, which are the ones the coach drafted
    off its own settles."""
    return [
        rule
        for rule in Rule.query.filter(Rule.retired_at.is_(None)).order_by(Rule.id).all()
        if (rule.source or {}).get("cut_id") == cut.id
    ]
