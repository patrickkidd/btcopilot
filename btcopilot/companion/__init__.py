from btcopilot.companion import (
    blueprint,
    events,
    fixtures,
    interactions,
    play,
    routes,
    sessions,
    settings,
)


def init_app(app):
    app.register_blueprint(blueprint.bp)
