import logging
import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def setup_telemetry(service_name: str, app=None) -> None:
    """Endpoint comes from OTEL_EXPORTER_OTLP_ENDPOINT
    (default http://localhost:4318)."""
    global _configured
    if not _configured:
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "1.0.0",
                "deployment.environment": os.getenv("DEPLOY_ENV", "local"),
            }
        )

        # Traces
        tp = TracerProvider(resource=resource)
        tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tp)

        # Metrics (exported every 10 s)
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(), export_interval_millis=10_000
        )
        metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[reader])
        )

        # Logs: bridge stdlib logging -> OTel
        lp = LoggerProvider(resource=resource)
        lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        set_logger_provider(lp)
        logging.getLogger().addHandler(
            LoggingHandler(level=logging.INFO, logger_provider=lp)
        )
        logging.getLogger().setLevel(logging.INFO)

        # Every httpx client (elevation, rainfall, run_store) is traced,
        # and the W3C `traceparent` header is injected automatically.
        HTTPXClientInstrumentor().instrument()
        _configured = True

    if app is not None:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
