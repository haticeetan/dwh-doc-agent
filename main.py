import uvicorn
from dotenv import load_dotenv
load_dotenv()  # OpenAI ve Oracle credential'larını yükle — import zincirinden önce çağrılmalı

from logger import setup_logging
setup_logging()  # JSON log formatını kur — diğer modüller import edilmeden önce

from api.router import app
from tracer import setup_tracing
setup_tracing(app)  # OTel TracerProvider'ı kur, FastAPI'yi enstrümanla

if __name__ == "__main__":
    uvicorn.run(
        "api.router:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )