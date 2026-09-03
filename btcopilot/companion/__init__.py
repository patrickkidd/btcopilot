from btcopilot.companion import blueprint, events, routes, sessions, settings


def init_app(app):
    app.register_blueprint(blueprint.bp)
