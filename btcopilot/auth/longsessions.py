import datetime

from flask.sessions import SecureCookieSessionInterface

from btcopilot.auth.signin import SESSION_TOKEN


class LongSessions(SecureCookieSessionInterface):
    """The training app pins the cookie to eight hours. A chat sign-in has to
    outlive that by months, so only sessions carrying a web session token get
    the long expiry and the training app's own policy is left alone."""

    def get_expiration_time(self, app, session):
        if session.permanent and SESSION_TOKEN in session:
            return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                days=app.config["CHAT_SESSION_DAYS"]
            )
        return super().get_expiration_time(app, session)
