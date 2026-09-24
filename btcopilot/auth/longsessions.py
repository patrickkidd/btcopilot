import datetime

from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature

from btcopilot.auth.signin import SESSION_TOKEN


class LongSessions(SecureCookieSessionInterface):
    """The training app pins the cookie to eight hours. A chat sign-in has to
    outlive that by months, so only sessions carrying a web session token get
    the long expiry and the training app's own policy is left alone.

    Reading is one cookie for both apps, so the signature is accepted for the
    chat months and each app then applies its own policy: the training app ages
    a session by its own stamp, and a chat session lives only as long as its
    server-side web session record."""

    def _chat_max_age(self, app) -> int:
        return int(
            datetime.timedelta(days=app.config["SESSION_DAYS"]).total_seconds()
        )

    def open_session(self, app, request):
        serializer = self.get_signing_serializer(app)
        if serializer is None:
            return None
        cookie = request.cookies.get(self.get_cookie_name(app))
        if not cookie:
            return self.session_class()
        try:
            return self.session_class(
                serializer.loads(cookie, max_age=self._chat_max_age(app))
            )
        except BadSignature:
            return self.session_class()

    def get_expiration_time(self, app, session):
        if session.permanent and SESSION_TOKEN in session:
            return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                days=app.config["SESSION_DAYS"]
            )
        return super().get_expiration_time(app, session)
