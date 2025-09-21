import uuid, datetime
import logging

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


_log = logging.getLogger(__name__)


class Session(db.Model, ModelMixin):
    __tablename__ = "sessions"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="sessions")

    token = Column(String(64), nullable=False, unique=True)

    def __init__(self, *args, token=None, **kwargs):
        if not token:
            token = self.generate_token()
        db.Model.__init__(self, *args, token=token, **kwargs)
        self.updated_at = datetime.datetime.utcnow()

    @staticmethod
    def generate_token():
        token = uuid.uuid4()
        unique = False
        while not unique:
            token = str(uuid.uuid4())
            if Session.query.filter_by(token=token).count() == 0:
                unique = True
        return token

    def account_editor_dict(self):
        from btcopilot.models import User, Policy
        from btcopilot import pro

        if not self.user.free_diagram:
            _log.info(f"Auto-adding free diagram to user {self.user.username}")
            self.user.set_free_diagram(_commit=True)

        ret = {
            "users": [u.as_dict() for u in User.query.filter_by(active=True)],
            "policies": [p.as_dict() for p in Policy.query.filter_by(public=True)],
            "deactivated_versions": pro.DEACTIVATED_VERSIONS,
        }
        if self.id:
            ret["session"] = self.as_dict(
                {
                    "user": self.user.as_dict(
                        {
                            "licenses": [
                                l.as_dict(
                                    {
                                        "activations": [
                                            a.as_dict({"machine": a.machine.as_dict()})
                                            for a in l.activations
                                        ],
                                        "policy": l.policy.as_dict(),
                                    },
                                )
                                for l in self.user.licenses
                            ],
                            "free_diagram": (
                                self.user.free_diagram.as_dict(
                                    exclude="data",
                                    include={
                                        "discussions": {
                                            "include": [
                                                "statements",
                                                "speakers",
                                            ]
                                        },
                                    },
                                )
                                if self.user.free_diagram
                                else None
                            ),
                        },
                    )
                }
            )
            # convert some non-standard object types that sneak in
            for discussion in ret["session"]["user"]["free_diagram"].get(
                "discussions", []
            ):
                for speaker in discussion.get("speakers", []):
                    speaker["type"] = speaker["type"].value
        else:
            ret["session"] = None
        return ret
