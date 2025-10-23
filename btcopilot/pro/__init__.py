import sys


# import pickle

IS_TEST = "pytest" in sys.modules

SESSION_EXPIRATION_DAYS = 30


# def scene_events(diagram_data):
#     events = []
#     data = pickle.loads(diagram_data['data'])
#     for item in data.get('items', []):
#         kind = item.get('kind')
#         if kind == 'Person':
#             events.append(item['birthEvent'])
#             events.append(item['adoptedEvent'])
#             events.append(item['deathEvent'])
#             events.extend(item['events'])
#         elif kind == 'Marriage':
#             events.extend(item['events'])
#         elif kind == 'Emotion':
#             events.append(item['startEvent'])
#             events.append(item['endEvent'])
#     return events


DEACTIVATED_VERSIONS = [
    # 'dev', # test
    "1.0.0b6",
    "1.0.0b7",
    "1.0.0b8",
    "1.0.0b9",
    "1.0.0b10",
    "1.0.0b11",
    "1.0.0b12",
    "1.0.0b13",
    "1.0.0b14",
    "1.0.0b15",
    "1.0.0b16",
    "1.0.0b17",
    "1.0.0b18",
    "1.0.0b19",
    "1.0.0b20",
    "1.0.0b21",
    "1.0.0b22",
    "1.0.0b23",
    "1.0.0b24",
    "1.0.0a12",
    "1.0.0a13",
    "1.0.0a14",
    "1.0.0a15",
    "1.0.0a16",
    "1.0.0a17",
    "1.0.0a18",
    "1.0.0a19",
    "1.0.0a20",
    "1.0.0a21",
    "1.0.0a22",
    "1.0.0b23",
    "1.0.0b24",
    "1.0.0a25",
    "1.0.0a26",
    "1.0.0a27",
    "1.1.0a1",
    "1.1.0a2",
    "1.1.0a3",
    "1.1.0a4",
    "1.1.0a5",
    "1.1.0a6",
    "1.1.1a0",
    "1.1.3a0",
    "1.1.3a1",
    "1.1.4a0",
    "1.1.4a1",
    "1.1.4a2",
    "1.1.4a3",
    "1.1.4a4",
    "1.1.4a5",
    "1.1.4a6",
    "1.1.4a7",
    "1.2.0a1",
    "1.2.0a2",
    "1.2.0a3",
    "1.2.0a4",
]


import uuid


def validate_uuid4(uuid_string):
    """
    Validate that a UUID string is in
    fact a valid uuid4.
    Happily, the uuid module does the actual
    checking for us.
    It is vital that the 'version' kwarg be passed
    to the UUID() call, otherwise any 32-character
    hex string is considered valid.
    """

    try:
        val = uuid.UUID(uuid_string, version=4)
    except ValueError:
        # If it's a value error, then the string
        # is not a valid hex code for a UUID.
        return False
    except:
        # pks: Well, if it's an error at all then it isn't valid
        return False

    # If the uuid_string is a valid hex code,
    # but an invalid uuid4,
    # the UUID.__init__ will convert it to a
    # valid uuid4. This is bad for validation purposes.

    return val.hex == uuid_string.replace("-", "")


from . import models
from . import routes


def init_app(app):
    routes.init_app(app)


def init_celery(celery):
    from . import tasks

    celery.task(tasks.sync_with_stripe, name="sync_with_stripe")
    celery.task(tasks._expire_stale_sessions, name="expire_stale_sessions")
