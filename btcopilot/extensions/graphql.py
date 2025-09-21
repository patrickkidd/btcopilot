from sqlalchemy.ext.declarative import declarative_base

import graphene as g
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from flask_graphql import GraphQLView
from flask import request
from werkzeug.exceptions import BadRequest, Unauthorized

from btcopilot.pro.models import (
    Session,
    User,
    License,
    Policy,
    Machine,
    Activation,
    Diagram,
)


class Session(SQLAlchemyObjectType):
    class Meta:
        model = Session

        # Automatically sets up connections
        # interfaces = (g.relay.Node,)

        # use `only_fields` to only expose specific fields ie "name"
        # only_fields = ("name",)
        # use `exclude_fields` to exclude specific fields ie "last_name"
        # exclude_fields = ("last_name",)


class User(SQLAlchemyObjectType):
    class Meta:
        model = User
        filter_fields = ["username"]
        interfaces = (g.relay.Node,)


class License(SQLAlchemyObjectType):
    class Meta:
        model = License


class Policy(SQLAlchemyObjectType):
    class Meta:
        model = Policy


class Machine(SQLAlchemyObjectType):
    class Meta:
        model = Machine


class Activation(SQLAlchemyObjectType):
    class Meta:
        model = Activation


class Diagram(SQLAlchemyObjectType):
    class Meta:
        model = Diagram


class Query(g.ObjectType):
    users = SQLAlchemyConnectionField(User)
    sessions = g.List(Session)
    licenses = g.List(License)
    policies = g.List(Policy)
    machines = g.List(Machine)
    activations = g.List(Activation)
    diagrams = g.List(Diagram)

    def resolve_users(self, info):
        return User.get_query(info).all()

    def resolve_sessions(self, info):
        return Session.get_query(info).all()

    def resolve_licenses(self, info):
        return License.get_query(info).all()

    def resolve_policies(self, info):
        return Policy.get_query(info).all()

    def resolve_machines(self, info):
        return Machine.get_query(info).all()

    def resolve_activations(self, info):
        return Activation.get_query(info).all()

    def resolve_sessions(self, info):
        return Session.get_query(info).all()


view = GraphQLView.as_view(
    "graphql",
    schema=g.Schema(query=Query, types=[User, License, Policy, Machine, Activation]),
    graphiql=True,
)


def authed(*args, **kwargs):
    if not "FD-User-Name" in request.headers:
        raise BadRequest("No username header")
    email = request.headers["FD-User-Name"]

    if not "FD-User-Secret" in request.headers:
        raise BadRequest("No authentication header")
    secret = request.headers["FD-User-Secret"]

    user = User.query.filter_by(username=email).one_or_none()
    if not user or user.secret != secret:
        raise Unauthorized("User is not authorized")

    # Only admin can access GraphQL API
    if "admin" != user.roles:
        raise Unauthorized("User has insufficient permissions")

    return view(*args, **kwargs)


def init_app(app):
    app.add_url_rule(
        "/graphql", view_func=authed, methods=["GET", "POST", "PUT", "DELETE"]
    )
