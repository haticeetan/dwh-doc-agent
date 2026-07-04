import functools
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_tracing(app=None) -> None:
    """
    Uygulama başlangıcında bir kez çağrılır (main.py).

    Ortam değişkenleri:
        OTEL_EXPORTER                 : "console" (varsayılan) | "otlp"
        OTEL_EXPORTER_OTLP_ENDPOINT   : OTLP HTTP endpoint
                                        varsayılan: http://localhost:4318/v1/traces
                                        Jaeger, Zipkin ve Azure Monitor bu protokolü destekler.

    FastAPI uygulaması geçilirse HTTP istekleri otomatik olarak span'lara dönüşür.
    """
    resource = Resource.create({SERVICE_NAME: "dw-docagent"})
    provider = TracerProvider(resource=resource)

    exporter_type = os.getenv("OTEL_EXPORTER", "console").lower()

    if exporter_type == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318/v1/traces",
        )
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        # /health her 30 saniyede bir frontend tarafından çağrılıyor — span gürültüsünü önlemek için hariç tutuluyor
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health")


def get_tracer(name: str) -> trace.Tracer:
    """Her modül bu fonksiyonla kendi tracer'ını alır."""
    return trace.get_tracer(name)


def trace_node(node_name: str):
    """
    LangGraph node fonksiyonlarını bir OTel span içine sarar.

    Her node çalıştığında otomatik olarak:
        - Span başlatılır (node.{node_name})
        - State'ten tablo adları, intent tipi ve retry sayısı attribute olarak eklenir
        - Exception oluşursa span'a kaydedilir ve status ERROR olarak işaretlenir
        - Node bitince span kapatılır

    Kullanım (agent/graph.py):
        graph.add_node("intent_parser", trace_node("intent_parser")(intent_parser_node))
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            tracer = get_tracer("agent.nodes")
            with tracer.start_as_current_span(f"node.{node_name}") as span:
                span.set_attribute("node.name", node_name)
                span.set_attribute("node.retry_count", state.get("retry_count", 0))

                tables = state.get("tables", [])
                if tables:
                    span.set_attribute("node.tables", ",".join(tables))

                intent = state.get("intent_type", "")
                if intent:
                    span.set_attribute("node.intent_type", intent)

                try:
                    result = fn(state)
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    raise

        return wrapper
    return decorator
