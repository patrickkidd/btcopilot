import time
from datetime import datetime
import hashlib
import urllib.parse
from werkzeug.datastructures import Headers
import wsgiref.handlers
import flask.testing

import vedana
from btcopilot import version
from btcopilot.pro.models import User


class FDEncryptionTestClient(flask.testing.FlaskClient):
    """Encrypt requests, decrypt responses."""

    def __init__(self, *args, **kwargs):
        # self._app = kwargs.pop("app")
        if "user" in kwargs:
            self._user_id = kwargs.pop("user").id
        else:
            self._user_id = None
        self._encrypted = kwargs.pop("encrypted", True)
        super().__init__(*args, **kwargs)

    # https://stackoverflow.com/questions/16416001/set-http-headers-for-all-requests-in-a-flask-test/16416587
    def open(self, *args, **kwargs):
        """Insert auth headers"""
        if self._user_id:
            _user = User.query.get(self._user_id)
            user = _user.username
            secret = _user.secret.encode("utf-8")
        else:
            user = vedana.ANON_USER
            secret = vedana.ANON_SECRET
        if kwargs["method"] in ["POST", "PUT"]:
            data = kwargs.get("data", b"")
        else:
            data = b""
        content_md5 = hashlib.md5(data).hexdigest()
        content_type = "application/json" if "json" in kwargs else "text/html"
        date = wsgiref.handlers.format_date_time(
            time.mktime(datetime.now().timetuple())
        )
        resource = args[0]
        parts = urllib.parse.urlparse(resource)
        # path = parts.path
        signature = vedana.sign(
            secret, kwargs["method"], content_md5, content_type, date, resource
        )
        auth_header = vedana.httpAuthHeader(user, signature)
        auth_headers = Headers(
            {
                "FD-Authentication": auth_header,
                "FD-Client-Version": version.VERSION,
                "Date": date,  # .encode('utf-8'),
                "Content-MD5": content_md5,  # .encode('utf-8'),
                "Content-Type": content_type,
            }
        )
        headers = kwargs.pop("headers", Headers())
        if isinstance(headers, dict):
            headers = Headers(headers)
        headers.extend(auth_headers)
        kwargs["headers"] = headers

        response = super().open(*args, **kwargs)

        return response
