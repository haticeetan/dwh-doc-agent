class DocAgentError(Exception):
    """Tüm uygulama hatalarının taban sınıfı."""
    pass


class DatabaseUnavailableError(DocAgentError):
    """Oracle veritabanına ulaşılamıyor (bağlantı hatası, pool tükenmesi, vb.)."""
    pass


class AIServiceError(DocAgentError):
    """OpenAI API'sine ulaşılamıyor veya yanıt vermiyor."""
    pass


class DocumentGenerationError(DocAgentError):
    """Döküman üretim pipeline'ı tamamlandı ama geçerli içerik üretilemedi."""
    pass


class DocumentNotFoundError(DocAgentError):
    """İstenen belge mevcut değil veya TTL süresi doldu."""
    pass
