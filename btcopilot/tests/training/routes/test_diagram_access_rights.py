import pytest
import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import User, Diagram, AccessRight


def test_get_access_rights_owner_can_view(auditor):
    """Test that diagram owner can view access rights"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()
    assert diagram, "Auditor should have a diagram"

    response = auditor.get(f"/training/diagrams/{diagram.id}/access-rights")

    assert response.status_code == 200
    assert response.json["success"] is True
    assert "access_rights" in response.json


def test_get_access_rights_admin_can_view_any(admin, test_user_2):
    """Test that admins can view access rights on any diagram"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    response = admin.get(f"/training/diagrams/{diagram.id}/access-rights")

    assert response.status_code == 200
    assert response.json["success"] is True


def test_get_access_rights_non_owner_denied(auditor, test_user_2):
    """Test that non-owners cannot view access rights"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    response = auditor.get(f"/training/diagrams/{diagram.id}/access-rights")

    assert response.status_code == 403


def test_grant_access_right_owner_can_grant(auditor, test_user_2):
    """Test that diagram owner can grant access rights"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()
    target_user = User.query.filter_by(username=test_user_2.username).first()

    response = auditor.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": target_user.id, "right": btcopilot.ACCESS_READ_ONLY},
    )

    assert response.status_code == 201
    assert response.json["success"] is True
    assert response.json["access_right"]["user_id"] == target_user.id
    assert response.json["access_right"]["right"] == btcopilot.ACCESS_READ_ONLY

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=target_user.id
    ).first()
    assert access_right is not None
    assert access_right.right == btcopilot.ACCESS_READ_ONLY


def test_grant_access_right_admin_can_grant_any(admin, test_user_2):
    """Test that admins can grant access rights on any diagram"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Create a third user to grant access to (can't grant to owner or admin themselves)
    third_user = User(
        username="third_user@test.com",
        roles=btcopilot.ROLE_AUDITOR,
        first_name="Third",
        last_name="User",
    )
    db.session.add(third_user)
    db.session.commit()

    response = admin.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": third_user.id, "right": btcopilot.ACCESS_READ_WRITE},
    )

    assert response.status_code == 201
    assert response.json["success"] is True


def test_grant_access_right_non_owner_denied(auditor, test_user_2):
    """Test that non-owners cannot grant access rights"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Create a third user to attempt to grant access to
    third_user = User(
        username="third_user@test.com",
        roles=btcopilot.ROLE_AUDITOR,
        first_name="Third",
        last_name="User",
    )
    db.session.add(third_user)
    db.session.commit()

    response = auditor.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": third_user.id, "right": btcopilot.ACCESS_READ_ONLY},
    )

    assert response.status_code == 403


def test_grant_access_right_cannot_grant_to_owner(auditor, test_user_2):
    """Test that you cannot grant access rights to the diagram owner"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()

    response = auditor.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": auditor.user.id, "right": btcopilot.ACCESS_READ_ONLY},
    )

    assert response.status_code == 400
    assert "owner" in response.json["error"].lower()


def test_grant_access_right_invalid_right(auditor, test_user_2):
    """Test that invalid access right values are rejected"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()
    target_user = User.query.filter_by(username=test_user_2.username).first()

    response = auditor.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": target_user.id, "right": "invalid"},
    )

    assert response.status_code == 400
    assert "invalid" in response.json["error"].lower()


def test_update_access_right(auditor, test_user_2):
    """Test that existing access rights can be updated"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()
    target_user = User.query.filter_by(username=test_user_2.username).first()

    diagram.grant_access(target_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    response = auditor.post(
        f"/training/diagrams/{diagram.id}/access-rights",
        json={"user_id": target_user.id, "right": btcopilot.ACCESS_READ_WRITE},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["access_right"]["right"] == btcopilot.ACCESS_READ_WRITE

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=target_user.id
    ).first()
    assert access_right.right == btcopilot.ACCESS_READ_WRITE


def test_revoke_access_right_owner_can_revoke(auditor, test_user_2):
    """Test that diagram owner can revoke access rights"""
    diagram = Diagram.query.filter_by(user_id=auditor.user.id).first()
    target_user = User.query.filter_by(username=test_user_2.username).first()

    diagram.grant_access(target_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=target_user.id
    ).first()
    assert access_right is not None

    response = auditor.delete(
        f"/training/diagrams/{diagram.id}/access-rights/{access_right.id}"
    )

    assert response.status_code == 200
    assert response.json["success"] is True

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=target_user.id
    ).first()
    assert access_right is None


def test_revoke_access_right_admin_can_revoke_any(admin, test_user_2):
    """Test that admins can revoke access rights on any diagram"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    # Create a third user to grant/revoke access to
    third_user = User(
        username="third_user@test.com",
        roles=btcopilot.ROLE_AUDITOR,
        first_name="Third",
        last_name="User",
    )
    db.session.add(third_user)
    db.session.commit()

    diagram.grant_access(third_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=third_user.id
    ).first()

    response = admin.delete(
        f"/training/diagrams/{diagram.id}/access-rights/{access_right.id}"
    )

    assert response.status_code == 200
    assert response.json["success"] is True


def test_revoke_access_right_non_owner_denied(auditor, test_user_2):
    """Test that non-owners cannot revoke access rights"""
    owner = User.query.filter_by(username=test_user_2.username).first()
    diagram = Diagram(user_id=owner.id, name="Owner's Diagram")
    db.session.add(diagram)
    db.session.commit()

    target_user = auditor.user
    diagram.grant_access(target_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram.id, user_id=target_user.id
    ).first()

    response = auditor.delete(
        f"/training/diagrams/{diagram.id}/access-rights/{access_right.id}"
    )

    assert response.status_code == 403


def test_revoke_access_right_wrong_diagram(auditor, test_user_2):
    """Test that access right must belong to the diagram"""
    diagram1 = Diagram.query.filter_by(user_id=auditor.user.id).first()

    diagram2 = Diagram(user_id=auditor.user.id, name="Second Diagram")
    db.session.add(diagram2)
    db.session.commit()

    target_user = User.query.filter_by(username=test_user_2.username).first()
    diagram2.grant_access(target_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    access_right = AccessRight.query.filter_by(
        diagram_id=diagram2.id, user_id=target_user.id
    ).first()

    response = auditor.delete(
        f"/training/diagrams/{diagram1.id}/access-rights/{access_right.id}"
    )

    assert response.status_code == 400
    assert "does not belong" in response.json["error"].lower()
