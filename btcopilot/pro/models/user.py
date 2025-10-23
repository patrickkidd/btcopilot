import datetime
import random
import string
import pickle

from sqlalchemy import Column, Boolean, String, Integer, ForeignKey, inspect, JSON
from sqlalchemy.orm import relationship
import flask_bcrypt

import vedana
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


def randomString(length=32):
    """Generate a random string of fixed length"""
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for i in range(length))


class User(db.Model, ModelMixin):
    __tablename__ = "users"

    IS_ANONYMOUS = False

    active = Column(Boolean, nullable=False, server_default="1")
    username = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False, server_default="")
    reset_password_code = Column(String(100))
    status = Column(String(64), nullable=False)  # ('pending', 'confirmed')

    # like an api secret returned when logging in and then used for authenticating requests.
    secret = Column(String(64), default=randomString)

    roles = Column(String(255), default=vedana.ROLE_SUBSCRIBER)

    first_name = Column(String(100), nullable=False, server_default="")
    last_name = Column(String(100), nullable=False, server_default="")

    stripe_id = Column(String(200))

    machines = relationship("Machine", back_populates="user")
    licenses = relationship("License", back_populates="user")
    sessions = relationship("Session", back_populates="user")
    diagrams = relationship(
        "Diagram", primaryjoin="Diagram.user_id == User.id", back_populates="user"
    )

    discussions = relationship("Discussion", back_populates="user")

    free_diagram_id = Column(Integer, ForeignKey("diagrams.id", use_alter=True))
    free_diagram = relationship(
        "Diagram", primaryjoin="Diagram.id == User.free_diagram_id"
    )

    def __init__(
        self, *args, password=None, reset_password_code=None, roles=None, **kwargs
    ):
        db.Model.__init__(self, *args, **kwargs)
        if password != None:
            self.set_password(password)
        if reset_password_code != None:
            self.set_reset_password_code(reset_password_code)
        if roles is not None:
            if not isinstance(roles, tuple):
                roles = (roles,)
            self.roles = ",".join(roles)
        if not "status" in kwargs:
            self.status = "pending"

        # self.is_authenticated = False
        # self.is_active = True
        # self.is_anonymous = False

    def __str__(self):
        return "<User id: %i, %s, %s>" % (self.id, self.full_name(), self.username)

    # Flask-Login
    # def get_id(self) -> str:
    #     """Flask-Login"""
    #     return str(self.id)

    # @staticmethod
    # def generate_reset_password_code(email):
    #     serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    #     return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])

    # @staticmethod
    # def confirm_reset_password_code(tokecode, expiration=3600):
    #     serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    #     try:
    #         email = serializer.loads(
    #             code,
    #             salt=app.config['SECURITY_PASSWORD_SALT'],
    #             max_age=expiration
    #         )
    #     except:
    #         return False
    #     return email

    def as_dict(self, update=None, include=None, exclude=None, only=None):
        if not exclude:
            exclude = ["password", "reset_password_code", "stripe_id"]
        ret = super().as_dict(update, include=include, exclude=exclude)
        ret["roles"] = ret["roles"].split(",")
        return ret

    def set_reset_password_code(self, plaintext):
        hashed = flask_bcrypt.generate_password_hash(plaintext).decode("utf8")
        self.reset_password_code = hashed

    def check_reset_password_code(self, plaintext: str):
        return flask_bcrypt.check_password_hash(self.reset_password_code, plaintext)

    def set_password(self, plaintext):
        hashed_password = flask_bcrypt.generate_password_hash(plaintext).decode("utf8")
        self.password = hashed_password
        self.reset_password_code = None

    def check_password(self, plaintext):
        return flask_bcrypt.check_password_hash(self.password, plaintext)

    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name)

    def set_role(self, role: str):
        self.roles = role

    def has_role(self, role: str):
        if role == vedana.ROLE_SUBSCRIBER:
            # Everyone is at least a subscriber"""
            return True

        my_roles = self.roles.split(",")
        if vedana.ROLE_ADMIN in my_roles:
            return True
        elif role in my_roles:
            return True
        else:
            return False

    def set_free_diagram(self, bdata=None, updated_at=None, _commit=False):
        from btcopilot.pro.models import Diagram

        if bdata is None:
            bdata = pickle.dumps({})

        if not self.free_diagram:
            diagram = Diagram(user_id=self.id, name="Free Diagram", data=bdata)
            db_session = inspect(self).session
            db_session.add(diagram)
            db_session.merge(diagram)
            self.update(free_diagram_id=diagram.id)
            db_session.merge(diagram)
            db_session.refresh(self)
        if updated_at is not None:
            _updated_at = updated_at
        else:
            _updated_at = datetime.datetime.utcnow()
        self.free_diagram.update(data=bdata, updated_at=_updated_at)
        if _commit:
            inspect(self).session.commit()
