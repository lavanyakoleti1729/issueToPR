from functools import lru_cache

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config.settings import get_settings


@lru_cache
def tracer():
    settings = get_settings()
    provider = TracerProvider(resource=Resource.create({"service.name": "issue-agent"}))
    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"
                )
            )
        )
    trace.set_tracer_provider(provider)
    return trace.get_tracer("issue-agent")
