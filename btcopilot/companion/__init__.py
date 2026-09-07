from btcopilot.companion import (
    blueprint,
    events,
    interactions,
    play,
    routes,
    sessions,
    settings,
    turn,
)


def init_app(app):
    app.register_blueprint(blueprint.bp)
