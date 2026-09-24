import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def provider() -> trace.TracerProvider:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return trace.NoOpTracerProvider()
    sdk = TracerProvider()
    sdk.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    return sdk


def init_app():
    trace.set_tracer_provider(provider())
