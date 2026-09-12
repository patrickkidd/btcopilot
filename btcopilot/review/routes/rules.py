"""Rules: the coding guidelines, one row each. Never deleted; retired
instead (R-0275). Anyone may flag one for the next meeting (R-0276)."""

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter
from btcopilot.review.models import Rule, RuleSource
from btcopilot.review.routes import admin, bp, coder


def payload(rule: Rule) -> dict:
    return rule.as_dict()


@bp.route("/rules")
def rule_index():
    """The live rules: everything not retired."""
    coder()
    found = Rule.query.filter(Rule.retired_at.is_(None)).order_by(Rule.id).all()
    return jsonify([payload(r) for r in found])


@bp.route("/rules", methods=["POST"])
def rule_create():
    user = coder()
    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        raise ValueError("a rule needs its words")
    rule = Rule(
        text=text,
        source=body.get("source") or {"user_id": user.id},
        drafted_by=RuleSource.Human,
        flags=[],
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(payload(rule)), 201


@bp.route("/rules/<int:rule_id>", methods=["PATCH"])
def rule_patch(rule_id: int):
    user = coder()
    rule = db.session.get(Rule, rule_id)
    if rule is None:
        return "no rule by that id", 404
    body = request.get_json() or {}
    flags = list(rule.flags or [])

    if body.get("flag"):
        flags.append(
            {
                "user_id": user.id,
                "reason": body.get("reason"),
                "flagged_at": adapter.utcnow().isoformat(),
            }
        )
    if body.get("close_flag"):
        flags = [
            (
                dict(f, closed_at=adapter.utcnow().isoformat())
                if f.get("user_id") == user.id and not f.get("closed_at")
                else f
            )
            for f in flags
        ]
    rule.flags = flags

    if body.get("ratified_at"):
        admin()
        rule.ratified_at = adapter.utcnow()
    if body.get("retired_at"):
        admin()
        rule.retired_at = adapter.utcnow()

    db.session.commit()
    return jsonify(payload(rule))
