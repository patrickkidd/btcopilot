# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import GenericRepr, Snapshot


snapshots = Snapshot()

snapshots['test_only[params0] 1'] = {
    'active': True,
    'created_at': GenericRepr('datetime.datetime(2025, 1, 15, 12, 0)'),
    'first_name': '',
    'free_diagram_id': None,
    'id': 1,
    'last_name': '',
    'roles': [
        'subscriber'
    ],
    'secret': 'some_secret',
    'status': 'pending',
    'updated_at': None,
    'username': 'something'
}

snapshots['test_only[params1] 1'] = {
    'active': True,
    'created_at': GenericRepr('datetime.datetime(2025, 1, 15, 12, 0)'),
    'first_name': '',
    'free_diagram_id': None,
    'id': 1,
    'last_name': '',
    'roles': [
        'subscriber'
    ],
    'secret': 'some_secret',
    'status': 'pending',
    'updated_at': None,
    'username': 'something'
}
