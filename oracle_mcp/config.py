import os
from dotenv import load_dotenv

load_dotenv()

# Oracle bağlantı bilgileri
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "1521")
DB_SERVICE = os.getenv("DB_SERVICE")   # Service Name kullanıyorsan doldur
DB_SID = os.getenv("DB_SID")           # SID kullanıyorsan doldur

# DSN string — ikisinden biri dolu olmalı
# Service Name : host:port/service_name
# SID          : host:port:sid
if DB_SID:
    DB_DSN = f"{DB_HOST}:{DB_PORT}:{DB_SID}"
elif DB_SERVICE:
    DB_DSN = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
else:
    raise ValueError(".env dosyasında DB_SID veya DB_SERVICE tanımlı olmalı")

# Oracle Instant Client dizini (Windows)
# Örnek: C:/oracle/instantclient_21_9
ORACLE_CLIENT_LIB = os.getenv("ORACLE_CLIENT_LIB")

# Bağlantı pool ayarları
POOL_MIN = int(os.getenv("POOL_MIN", "2"))
POOL_MAX = int(os.getenv("POOL_MAX", "10"))
POOL_INCREMENT = int(os.getenv("POOL_INCREMENT", "1"))

# Agent ayarları
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))