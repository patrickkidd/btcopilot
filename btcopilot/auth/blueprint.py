import logging

from flask import Blueprint, request
from flask_wtf.csrf import CSRFError, generate_csrf

from btcopilot.extensions import csrf

_log = logging.getLogger(__name__)

bp = Blueprint("chatauth", __name__, template_folder="templates")


@bp.before_request
def _protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf.protect()


@bp.errorhandler(CSRFError)
def _csrf_error(e):
    _log.warning(f"CSRF error: {e.description} from {request.remote_addr}")
    return e.description, 400


@bp.context_processor
def _inject_globals():
    return {"csrf_token": generate_csrf}
