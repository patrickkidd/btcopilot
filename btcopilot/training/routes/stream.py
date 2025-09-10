import logging
import queue
from datetime import datetime
from flask import Blueprint, jsonify, Response

from ..auth import require_auditor_or_admin
from ..sse import sse_manager

_log = logging.getLogger(__name__)

# Create the stream blueprint
stream_bp = Blueprint(
    "stream",
    __name__,
    url_prefix="/stream",
)


@stream_bp.route("/")
@require_auditor_or_admin
def stream():
    """Server-sent events for real-time updates"""

    _log.info(f"New SSE client connected")

    def event_stream():
        q = sse_manager.subscribe()
        _log.info(
            f"SSE client subscribed, total subscribers: {len(sse_manager.subscribers)}"
        )

        # Send initial connection message
        yield 'data: {"type": "connected", "message": "SSE connection established"}\n\n'

        try:
            while True:
                try:
                    message = q.get(timeout=30)
                    _log.info(f"Sending SSE message: {message}")
                    yield f"data: {message}\n\n"
                except queue.Empty:
                    # Send heartbeat
                    _log.debug("Sending SSE heartbeat")
                    yield 'data: {"type": "ping"}\n\n'
        except GeneratorExit:
            _log.info("SSE client disconnected")
            pass
        finally:
            sse_manager.unsubscribe(q)
            _log.info(
                f"SSE client unsubscribed, remaining subscribers: {len(sse_manager.subscribers)}"
            )

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Cache-Control"
    response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering
    return response


@stream_bp.route("/test-sse")
@require_auditor_or_admin
def test_sse():
    """Test endpoint to manually trigger SSE messages"""

    import json

    test_message = {
        "type": "test",
        "message": "Manual SSE test",
        "timestamp": datetime.now().isoformat(),
    }
    sse_manager.publish(json.dumps(test_message))
    return jsonify(
        {
            "message": "Test SSE message sent",
            "subscribers": len(sse_manager.subscribers),
        }
    )