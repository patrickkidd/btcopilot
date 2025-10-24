import os
import sys
import logging
from flask.cli import FlaskGroup
from btcopilot.app import create_app

# flask still reads the deprecated FLASK_ENV and loads that config file.
# So just override it from our FLASK_CONFIG
if os.getenv("FLASK_CONFIG"):
    os.environ["FLASK_ENV"] = os.getenv("FLASK_CONFIG")


app = create_app()


if __name__ == "__main__":

    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

    logging.getLogger().info(
        f"Usage: python manage.py --app btcopilot utils create-professional-annual-license"
    )

    # cli = FlaskGroup(create_app=btcopilot.create_app)
    cli = FlaskGroup(app)
    cli()
