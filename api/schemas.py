from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    consent: str = ""  # "yes" | "no" | "" — Evet/Hayır butonu tıklandığında dolar


class ChatResponse(BaseModel):
    reply: str
    intent: str                  # "chitchat" | "discovery" | "document"
    job_id: Optional[str] = None # Sadece document intent'inde dolu
    format: Optional[str] = None # "docx" | "pdf"


class DownloadResponse(BaseModel):
    job_id: str
    filename: str
    format: str


class ConversationSummary(BaseModel):
    session_id: str
    title: str
    last_message_at: str


class ConversationMessage(BaseModel):
    role: str
    content: str
    intent: Optional[str] = None
    created_at: str


class ProblemDetail(BaseModel):
    """
    RFC 7807 — Problem Details for HTTP APIs.

    Tüm hata yanıtları bu formatta döner. Content-Type: application/problem+json

    Alanlar:
        type           : Hata kategorisini tanımlayan URN (makine okunabilir)
        title          : Kısa, sabit başlık (hata sınıfı değişmezse değişmez)
        status         : HTTP durum kodu
        detail         : Kullanıcıya gösterilebilir, bu olaya özgü açıklama
        instance       : Hatanın oluştuğu endpoint
        correlation_id : Log satırlarıyla eşleştirme için istek ID'si
    """
    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlation_id: Optional[str] = None