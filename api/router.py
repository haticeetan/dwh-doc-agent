import os
import uuid

import oracledb
from openai import APIError as OpenAIAPIError
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from opentelemetry import trace as otel_trace

from api.schemas import ChatRequest, ChatResponse, ConversationSummary, ConversationMessage
from api.exceptions import DocumentGenerationError, DocumentNotFoundError
from agent.conversation_store import add_message, get_sessions, get_session_messages
from api.error_handlers import (
    handle_circuit_open,
    handle_database_unavailable,
    handle_document_generation_error,
    handle_document_not_found,
    handle_http_exception,
    handle_oracle_error,
    handle_openai_error,
    handle_unhandled_exception,
    handle_validation_error,
)
from agent.graph import build_graph
from output.file_server import generate_document, get_file_path, get_file_extension
from logger import get_logger, correlation_id
from resilience import CircuitOpenError
from tracer import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)

app = FastAPI(title="DW-DocAgent API", version="1.0.0")

# ── Exception handler'ları — özelden genele sıralanmalı ──────────────────────
app.add_exception_handler(DocumentNotFoundError,     handle_document_not_found)
app.add_exception_handler(DocumentGenerationError,   handle_document_generation_error)
app.add_exception_handler(CircuitOpenError,          handle_circuit_open)
app.add_exception_handler(oracledb.DatabaseError,    handle_oracle_error)
app.add_exception_handler(OpenAIAPIError,            handle_openai_error)
app.add_exception_handler(HTTPException,             handle_http_exception)
app.add_exception_handler(RequestValidationError,    handle_validation_error)
app.add_exception_handler(Exception,                 handle_unhandled_exception)

_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Her isteğe bir ID atar ve tüm log satırlarına bunu ekler.

    OTel aktifse mevcut span'ın trace_id'sini kullanır — böylece log satırları
    ve Jaeger/Zipkin span'ları aynı ID'yi taşır, ikisi arasında kolayca geçiş yapılır.
    OTel pasifse veya span geçersizse yeni bir UUID üretilir.
    """
    req_id = request.headers.get("X-Request-ID", "")
    if not req_id:
        ctx = otel_trace.get_current_span().get_span_context()
        if ctx.is_valid:
            req_id = format(ctx.trace_id, "032x")
        else:
            req_id = str(uuid.uuid4())

    correlation_id.set(req_id)

    is_health_check = request.url.path == "/health"
    if not is_health_check:
        logger.info(f"{request.method} {request.url.path} başladı")

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id

    if not is_health_check:
        logger.info(f"{request.method} {request.url.path} tamamlandı — HTTP {response.status_code}")

    return response


graph = build_graph()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Her mesajı grafa gönderir. intent_parser_node mesajı sınıflandırır:
      - chitchat  → chitchat_response'u metin olarak döner, dosya yok
      - discovery → discovery_result'u metin olarak döner, dosya yok
      - document  → doküman üretir, job_id ile indirme linki döner
    """
    session_id = request.session_id or str(uuid.uuid4())

    # Kullanıcı mesajını geçmişe ekle — consent yanıtları geçmişe yazılmıyor
    if not request.consent:
        add_message(session_id, "user", request.message)

    initial_state = {
        "session_id": session_id,
        "consent": request.consent,
        "message": request.message,
        "intent_type": "",
        "chitchat_response": "",
        "discovery_result": "",
        "tables": [],
        "output_format": "docx",
        "waiting_consent": False,
        "use_sample_data": False,
        "consent_question": "",
        "schemas": {},
        "lineage": {},
        "sample_data": {},
        "draft_docs": {},
        "quality_scores": {},
        "final_markdown": "",
        "approved": False,
        "retry_count": 0,
    }

    with tracer.start_as_current_span("langgraph.invoke") as span:
        span.set_attribute("message.length", len(request.message))
        graph_result = graph.invoke(initial_state)
        intent_type = graph_result.get("intent_type", "document")
        span.set_attribute("intent_type", intent_type)
        tables = graph_result.get("tables", [])
        if tables:
            span.set_attribute("tables", ",".join(tables))

    def _respond(response: ChatResponse, assistant_text: str, intent: str = "") -> ChatResponse:
        """Yanıtı intent bilgisiyle birlikte geçmişe kaydedip döner."""
        add_message(session_id, "assistant", assistant_text[:800], intent=intent)
        return response

    # ── Onay bekleniyor ───────────────────────────────────────────────────────
    if graph_result.get("waiting_consent"):
        question = graph_result.get("consent_question", "")
        return _respond(ChatResponse(reply=question, intent="awaiting_consent"), question, "awaiting_consent")

    # ── Chitchat ──────────────────────────────────────────────────────────────
    if intent_type == "chitchat":
        reply = graph_result.get("chitchat_response", "")
        return _respond(ChatResponse(reply=reply, intent="chitchat"), reply, "chitchat")

    # ── Discovery ─────────────────────────────────────────────────────────────
    if intent_type == "discovery":
        reply = graph_result.get("discovery_result", "")
        return _respond(ChatResponse(reply=reply, intent="discovery"), reply, "discovery")

    # ── Table info ────────────────────────────────────────────────────────────
    if intent_type == "table_info":
        reply = graph_result.get("discovery_result", "")
        return _respond(ChatResponse(reply=reply, intent="discovery"), reply, "discovery")

    # ── Document ──────────────────────────────────────────────────────────────
    tables = graph_result.get("tables", [])
    final_markdown = graph_result.get("final_markdown", "")
    output_format = graph_result.get("output_format", "docx")
    quality_scores = graph_result.get("quality_scores", {})

    if not final_markdown:
        raise DocumentGenerationError("Graph tamamlandı ancak final_markdown boş")

    title = ", ".join(tables) if tables else "dokümantasyon"
    job_id = generate_document(final_markdown, output_format, title)

    score_text = ""
    if quality_scores:
        scores = [f"{t}: {s:.2f}" for t, s in quality_scores.items()]
        score_text = f"\n\n📊 Kalite skorları: {', '.join(scores)}"

    reply = (
        f"**{', '.join(tables)}** tablosu için dokümantasyon hazır! ✅"
        f"{score_text}\n\n"
        f"Aşağıdaki butona basarak indirebilirsin."
    )

    return _respond(
        ChatResponse(reply=reply, intent="document", job_id=job_id, format=output_format),
        f"{', '.join(tables)} tablosu için dokümantasyon oluşturuldu.",
        "document",
    )


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    return get_sessions()


@app.get("/conversations/{session_id}/messages", response_model=list[ConversationMessage])
async def conversation_messages(session_id: str):
    return get_session_messages(session_id)


@app.get("/download/{job_id}")
async def download(job_id: str):
    path = get_file_path(job_id)
    if not path or not os.path.exists(path):
        raise DocumentNotFoundError(f"job_id={job_id}")

    ext = get_file_extension(job_id)
    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf":  "application/pdf",
    }

    return FileResponse(
        path=path,
        media_type=media_types.get(ext, "application/octet-stream"),
        filename=f"{job_id}.{ext}",
        headers={"Content-Disposition": f"attachment; filename={job_id}.{ext}"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DW-DocAgent"}
