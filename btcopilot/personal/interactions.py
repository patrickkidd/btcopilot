"""Every tap is learning data (R-0077): the looks that send nothing, the chips
that speak, the plays."""

from flask import abort

from btcopilot.extensions import db
from btcopilot.personal.models import Interaction, InteractionKind
from btcopilot.pro.models import Diagram
from btcopilot.schema import ItemKind


def recent(diagram_id: int, n: int = 50) -> list[Interaction]:
    return (
        Interaction.query.filter_by(diagram_id=diagram_id)
        .order_by(Interaction.id.desc())
        .limit(n)
        .all()
    )


def record_interaction(user, data: dict) -> Interaction:
    """Write one tap against the diagram it touched."""
    diagram = Diagram.query.get(data["diagram_id"])
    if not diagram:
        abort(404)
    if not diagram.check_read_access(user):
        abort(403)

    interaction = Interaction(
        diagram_id=diagram.id,
        user_id=user.id,
        session_id=data.get("session_id"),
        statement_id=data.get("statement_id"),
        kind=InteractionKind(data["kind"]),
        item_kind=ItemKind(data["item_kind"]),
        item_id=str(data["item_id"]) if data.get("item_id") is not None else None,
    )
    db.session.add(interaction)
    db.session.commit()
    return interaction
