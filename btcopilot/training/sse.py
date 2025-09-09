"""
Server-sent events manager for real-time updates in training interface.

Provides SSE functionality for real-time notifications about feedback submissions,
approvals, and other training-related events. Uses stand-in implementation that
should be extended by parent application.
"""

import logging
import json
import queue
import threading

_log = logging.getLogger(__name__)


class SSEManager:
    """Server-sent events manager - stand-in implementation"""
    
    def __init__(self):
        self.subscribers = []
        self._lock = threading.Lock()

    def subscribe(self):
        """Subscribe to SSE events - stand-in implementation"""
        q = queue.Queue()
        with self._lock:
            self.subscribers.append(q)
        _log.info(f"New SSE subscriber added. Total: {len(self.subscribers)}")
        return q

    def unsubscribe(self, q):
        """Unsubscribe from SSE events"""
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)
        _log.info(f"SSE subscriber removed. Total: {len(self.subscribers)}")

    def publish(self, message):
        """Publish message to all subscribers"""
        _log.info(
            f"Publishing SSE message to {len(self.subscribers)} subscribers: {message}"
        )
        with self._lock:
            dead_queues = []
            for q in self.subscribers:
                try:
                    q.put(message, block=False)
                    _log.debug(f"Message queued successfully")
                except queue.Full:
                    _log.warning(f"Queue full, removing subscriber")
                    dead_queues.append(q)
            
            # Clean up dead queues
            for q in dead_queues:
                self.subscribers.remove(q)
        
        _log.info(
            f"SSE message published to {len(self.subscribers) - len(dead_queues)} active subscribers"
        )

    def get_stream(self):
        """Get SSE stream generator - stand-in implementation"""
        q = self.subscribe()
        try:
            while True:
                try:
                    # Wait for message with timeout
                    message = q.get(timeout=30)
                    yield f"data: {message}\n\n"
                except queue.Empty:
                    # Send keepalive
                    yield "data: {\"type\": \"keepalive\"}\n\n"
        except GeneratorExit:
            self.unsubscribe(q)

    def publish_feedback_event(self, event_type, **kwargs):
        """Publish feedback-related event"""
        event_data = {
            "type": event_type,
            "timestamp": kwargs.get("timestamp"),
            **kwargs
        }
        self.publish(json.dumps(event_data))


# Global SSE manager instance
sse_manager = SSEManager()