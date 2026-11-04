import atexit
import logging

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from backend.database.session import engine

logger = logging.getLogger(__name__)


def setup_telemetry(app):
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)

    # Drain the batch processor before Python closes stdout/stderr. Without
    # this hook its worker thread can emit a logging error during interpreter
    # shutdown while flushing the final spans.
    atexit.register(provider.shutdown)

    logger.info("OpenTelemetry tracing initialized")
    return provider
