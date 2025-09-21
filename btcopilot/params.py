"""
HTTP parameter parsing. Methods should return a valid value or throw an
exception.
"""

import datetime as dt
import dateutil.parser


def datetime(x):
    if isinstance(x, dt.datetime):
        return x
    elif isinstance(x, str):
        return dateutil.parser.parse(x)


def truthy(x):
    if isinstance(x, str):
        return x in ["true", "True", "yes", "1"]
    else:
        return bool(x)


def pks(x):
    if isinstance(x, str):
        pks = [int(x) for x in set(x.split(","))]
    elif isinstance(x, int):
        pks = [x]
    else:
        pks = set(x)
    return pks


def integer(x):
    if isinstance(x, str):
        return int(x)
    else:
        return x
