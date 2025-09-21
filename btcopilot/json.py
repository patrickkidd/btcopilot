"""
json module that can handle more types.
"""

import datetime as py_datetime
from flask import json as flask_json

from btcopilot import params


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (py_datetime.datetime, py_datetime.date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def dumps(data, *args, **kwargs):
    return flask_json.dumps(data, *args, default=json_serializer, **kwargs)


def json_object_hook(json_dict):
    def _do_recursive(obj):
        for key, value in obj.items():
            if isinstance(value, dict):
                _do_recursive(value)
            elif isinstance(value, (int, float)):
                pass
            else:
                try:
                    # obj[key] = py_datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                    obj[key] = params.datetime(value)
                except:
                    pass

    _do_recursive(json_dict)
    return json_dict


def loads(sdata, *args, **kwargs):
    return flask_json.loads(sdata, *args, object_hook=json_object_hook, **kwargs)
