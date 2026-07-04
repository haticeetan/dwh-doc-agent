"""
DW-DocAgent Test Şeması — Oracle'da örnek veri ambarı tabloları oluşturur.

Senaryo: Bir perakende şirketinin veri ambarı
    - DIM_CUSTOMER   : Müşteri boyut tablosu
    - DIM_PRODUCT    : Ürün boyut tablosu
    - DIM_DATE       : Tarih boyut tablosu
    - FACT_SALES     : Satış fakt tablosu (FK ile bağlı)
    - FACT_RETURNS   : İade fakt tablosu (FK YOK — dep_tracer implicit test için)

Çalıştırma:
    python tests/create_test_schema.py
"""

import sys
from oracle_mcp.oracle_client import get_connection

# ── Önce varsa düşür, sonra oluştur ──────────────────────────────────────────
DROP_STATEMENTS = [
    "DROP TABLE FACT_RETURNS",
    "DROP TABLE FACT_SALES",
    "DROP TABLE DIM_DATE",
    "DROP TABLE DIM_PRODUCT",
    "DROP TABLE DIM_CUSTOMER",
]

CREATE_STATEMENTS = [

    # ── DIM_CUSTOMER ──────────────────────────────────────────────────────────
    """
    CREATE TABLE DIM_CUSTOMER (
        CUSTOMER_ID     NUMBER(10)      PRIMARY KEY,
        FIRST_NAME      VARCHAR2(50)    NOT NULL,
        LAST_NAME       VARCHAR2(50)    NOT NULL,
        EMAIL           VARCHAR2(100),
        PHONE           VARCHAR2(20),
        CITY            VARCHAR2(50),
        COUNTRY         VARCHAR2(50)    DEFAULT 'Turkey',
        SEGMENT         VARCHAR2(20),   -- 'RETAIL', 'WHOLESALE', 'ONLINE'
        IS_ACTIVE       NUMBER(1)       DEFAULT 1,
        CREATED_DATE    DATE            DEFAULT SYSDATE
    )
    """,

    # ── DIM_PRODUCT ───────────────────────────────────────────────────────────
    """
    CREATE TABLE DIM_PRODUCT (
        PRODUCT_ID      NUMBER(10)      PRIMARY KEY,
        PRODUCT_CODE    VARCHAR2(20)    NOT NULL UNIQUE,
        PRODUCT_NAME    VARCHAR2(100)   NOT NULL,
        CATEGORY        VARCHAR2(50),
        SUBCATEGORY     VARCHAR2(50),
        UNIT_PRICE      NUMBER(10,2),
        COST_PRICE      NUMBER(10,2),
        UNIT_OF_MEASURE VARCHAR2(20),   -- 'PIECE', 'KG', 'LITER'
        IS_ACTIVE       NUMBER(1)       DEFAULT 1,
        CREATED_DATE    DATE            DEFAULT SYSDATE
    )
    """,

    # ── DIM_DATE ──────────────────────────────────────────────────────────────
    """
    CREATE TABLE DIM_DATE (
        DATE_ID         NUMBER(8)       PRIMARY KEY,  -- YYYYMMDD formatında
        FULL_DATE       DATE            NOT NULL,
        DAY_OF_WEEK     NUMBER(1),      -- 1=Pazartesi, 7=Pazar
        DAY_NAME        VARCHAR2(10),
        WEEK_NUMBER     NUMBER(2),
        MONTH_NUMBER    NUMBER(2),
        MONTH_NAME      VARCHAR2(10),
        QUARTER         NUMBER(1),
        YEAR            NUMBER(4),
        IS_WEEKEND      NUMBER(1)       DEFAULT 0,
        IS_HOLIDAY      NUMBER(1)       DEFAULT 0
    )
    """,

    # ── FACT_SALES (FK tanımlı) ───────────────────────────────────────────────
    """
    CREATE TABLE FACT_SALES (
        SALE_ID         NUMBER(15)      PRIMARY KEY,
        DATE_ID         NUMBER(8)       NOT NULL,
        CUSTOMER_ID     NUMBER(10)      NOT NULL,
        PRODUCT_ID      NUMBER(10)      NOT NULL,
        QUANTITY        NUMBER(10)      NOT NULL,
        UNIT_PRICE      NUMBER(10,2)    NOT NULL,
        DISCOUNT_RATE   NUMBER(5,2)     DEFAULT 0,
        NET_AMOUNT      NUMBER(12,2),
        TAX_AMOUNT      NUMBER(10,2),
        TOTAL_AMOUNT    NUMBER(12,2)    NOT NULL,
        CHANNEL         VARCHAR2(20),   -- 'STORE', 'ONLINE', 'PHONE'
        STORE_ID        NUMBER(10),     -- FK YOK — implicit relation testi
        CREATED_DATE    DATE            DEFAULT SYSDATE,

        CONSTRAINT fk_sales_date
            FOREIGN KEY (DATE_ID)     REFERENCES DIM_DATE(DATE_ID),
        CONSTRAINT fk_sales_customer
            FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMER(CUSTOMER_ID),
        CONSTRAINT fk_sales_product
            FOREIGN KEY (PRODUCT_ID)  REFERENCES DIM_PRODUCT(PRODUCT_ID)
    )
    """,

    # ── FACT_RETURNS (FK YOK — implicit relation testi) ──────────────────────
    # CUSTOMER_ID, PRODUCT_ID, DATE_ID kolonları var ama FK tanımlı değil
    # dep_tracer'ın implicit_relations özelliğini test etmek için
    """
    CREATE TABLE FACT_RETURNS (
        RETURN_ID       NUMBER(15)      PRIMARY KEY,
        SALE_ID         NUMBER(15),     -- FACT_SALES'a implicit bağlı, FK yok
        DATE_ID         NUMBER(8),      -- DIM_DATE'e implicit bağlı, FK yok
        CUSTOMER_ID     NUMBER(10),     -- DIM_CUSTOMER'a implicit bağlı, FK yok
        PRODUCT_ID      NUMBER(10),     -- DIM_PRODUCT'a implicit bağlı, FK yok
        QUANTITY        NUMBER(10),
        RETURN_REASON   VARCHAR2(200),  -- 'DEFECTIVE', 'WRONG_ITEM', 'CHANGED_MIND'
        REFUND_AMOUNT   NUMBER(12,2),
        STATUS          VARCHAR2(20),   -- 'PENDING', 'APPROVED', 'REJECTED'
        CREATED_DATE    DATE            DEFAULT SYSDATE
    )
    """
]

# ── Comment'ler ───────────────────────────────────────────────────────────────
COMMENT_STATEMENTS = [
    # Tablo comment'leri
    "COMMENT ON TABLE DIM_CUSTOMER IS 'Müşteri boyut tablosu. Tüm müşteri demografik ve segment bilgilerini içerir.'",
    "COMMENT ON TABLE DIM_PRODUCT  IS 'Ürün boyut tablosu. Ürün hiyerarşisi, fiyat ve maliyet bilgilerini içerir.'",
    "COMMENT ON TABLE DIM_DATE     IS 'Tarih boyut tablosu. YYYYMMDD formatında DATE_ID ile takvim hiyerarşisini tutar.'",
    "COMMENT ON TABLE FACT_SALES   IS 'Satış fakt tablosu. Her satır bir satış işlemini temsil eder.'",
    "COMMENT ON TABLE FACT_RETURNS IS 'İade fakt tablosu. Satışlara karşılık gelen iade kayıtlarını tutar. NOT: FK constraint tanımlı değil.'",

    # DIM_CUSTOMER kolon comment'leri
    "COMMENT ON COLUMN DIM_CUSTOMER.SEGMENT   IS 'Müşteri segmenti: RETAIL, WHOLESALE veya ONLINE'",
    "COMMENT ON COLUMN DIM_CUSTOMER.IS_ACTIVE IS '1=Aktif müşteri, 0=Pasif/silinmiş müşteri'",

    # DIM_PRODUCT kolon comment'leri
    "COMMENT ON COLUMN DIM_PRODUCT.IS_ACTIVE IS '1=Satışta, 0=Üretimden kalkmış'",

    # DIM_DATE kolon comment'leri
    "COMMENT ON COLUMN DIM_DATE.DATE_ID    IS 'Birincil anahtar. YYYYMMDD formatında sayısal tarih kodu. Örn: 20240115'",
    "COMMENT ON COLUMN DIM_DATE.IS_WEEKEND IS '1=Hafta sonu (Cumartesi/Pazar), 0=Hafta içi'",
    "COMMENT ON COLUMN DIM_DATE.IS_HOLIDAY IS '1=Resmi tatil, 0=Normal gün'",

    # FACT_SALES kolon comment'leri
    "COMMENT ON COLUMN FACT_SALES.CHANNEL  IS 'Satış kanalı: STORE=Mağaza, ONLINE=E-ticaret, PHONE=Telefon'",
    "COMMENT ON COLUMN FACT_SALES.STORE_ID IS 'Mağaza ID. DIM_STORE tablosuna bağlanacak, henüz FK tanımlı değil.'",

    # FACT_RETURNS kolon comment'leri
    "COMMENT ON COLUMN FACT_RETURNS.STATUS        IS 'İade durumu: PENDING=Bekliyor, APPROVED=Onaylandı, REJECTED=Reddedildi'",
    "COMMENT ON COLUMN FACT_RETURNS.RETURN_REASON IS 'İade nedeni: DEFECTIVE=Hatalı ürün, WRONG_ITEM=Yanlış ürün, CHANGED_MIND=Fikir değişikliği'",
]

# ── Örnek veri ────────────────────────────────────────────────────────────────
SAMPLE_DATA = [
    # DIM_DATE
    "INSERT INTO DIM_DATE VALUES (20240101, DATE '2024-01-01', 1, 'Pazartesi', 1,  1, 'Ocak',    1, 2024, 0, 1)",
    "INSERT INTO DIM_DATE VALUES (20240115, DATE '2024-01-15', 1, 'Pazartesi', 3,  1, 'Ocak',    1, 2024, 0, 0)",
    "INSERT INTO DIM_DATE VALUES (20240120, DATE '2024-01-20', 6, 'Cumartesi', 3,  1, 'Ocak',    1, 2024, 1, 0)",
    "INSERT INTO DIM_DATE VALUES (20240215, DATE '2024-02-15', 4, 'Perşembe', 7,   2, 'Şubat',   1, 2024, 0, 0)",
    "INSERT INTO DIM_DATE VALUES (20240310, DATE '2024-03-10', 7, 'Pazar',    10,  3, 'Mart',    1, 2024, 1, 0)",

    # DIM_CUSTOMER
    "INSERT INTO DIM_CUSTOMER VALUES (1, 'Ahmet',   'Yılmaz',  'ahmet@email.com',  '5551234567', 'İstanbul', 'Turkey', 'RETAIL',    1, SYSDATE)",
    "INSERT INTO DIM_CUSTOMER VALUES (2, 'Fatma',   'Kaya',    'fatma@email.com',  '5557654321', 'Ankara',   'Turkey', 'WHOLESALE', 1, SYSDATE)",
    "INSERT INTO DIM_CUSTOMER VALUES (3, 'Mehmet',  'Demir',   'mehmet@email.com', '5559876543', 'İzmir',    'Turkey', 'ONLINE',    1, SYSDATE)",
    "INSERT INTO DIM_CUSTOMER VALUES (4, 'Zeynep',  'Çelik',   NULL,               '5554567890', 'Bursa',    'Turkey', 'RETAIL',    0, SYSDATE)",
    "INSERT INTO DIM_CUSTOMER VALUES (5, 'Ali',     'Şahin',   'ali@email.com',    NULL,         'Antalya',  'Turkey', 'ONLINE',    1, SYSDATE)",

    # DIM_PRODUCT
    "INSERT INTO DIM_PRODUCT VALUES (1, 'PRD-001', 'Laptop 15',       'Elektronik', 'Bilgisayar', 15000, 10000, 'PIECE', 1, SYSDATE)",
    "INSERT INTO DIM_PRODUCT VALUES (2, 'PRD-002', 'Kablosuz Mouse',  'Elektronik', 'Aksesuar',     350,   200, 'PIECE', 1, SYSDATE)",
    "INSERT INTO DIM_PRODUCT VALUES (3, 'PRD-003', 'Mekanik Klavye',  'Elektronik', 'Aksesuar',     850,   500, 'PIECE', 1, SYSDATE)",
    "INSERT INTO DIM_PRODUCT VALUES (4, 'PRD-004', 'USB Hub',         'Elektronik', 'Aksesuar',     250,   120, 'PIECE', 1, SYSDATE)",
    "INSERT INTO DIM_PRODUCT VALUES (5, 'PRD-005', 'Monitör 27',      'Elektronik', 'Ekran',       8500,  5500, 'PIECE', 0, SYSDATE)",

    # FACT_SALES
    "INSERT INTO FACT_SALES VALUES (1001, 20240115, 1, 1, 1, 15000, 5,  14250,  2565, 16815, 'STORE',  10, SYSDATE)",
    "INSERT INTO FACT_SALES VALUES (1002, 20240115, 2, 2, 3,   350, 0,   1050,   189,  1239, 'ONLINE', 11, SYSDATE)",
    "INSERT INTO FACT_SALES VALUES (1003, 20240120, 3, 3, 1,   850, 10,   765,   137.7, 902.7,'STORE', 10, SYSDATE)",
    "INSERT INTO FACT_SALES VALUES (1004, 20240215, 1, 4, 2,   250, 0,    500,    90,   590, 'PHONE',  NULL, SYSDATE)",
    "INSERT INTO FACT_SALES VALUES (1005, 20240310, 5, 2, 5,   350, 15,  1487.5, 267.75, 1755.25, 'ONLINE', 12, SYSDATE)",

    # FACT_RETURNS
    "INSERT INTO FACT_RETURNS VALUES (2001, 1003, 20240310, 3, 3, 1, 'DEFECTIVE',    765,   'APPROVED', SYSDATE)",
    "INSERT INTO FACT_RETURNS VALUES (2002, 1001, 20240215, 1, 1, 1, 'CHANGED_MIND', 14250, 'PENDING',  SYSDATE)",
]


def run():
    print("=" * 55)
    print("DW-DocAgent — Test Şeması Oluşturuluyor")
    print("=" * 55)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Varsa düşür
        print("\n[1/4] Mevcut tablolar temizleniyor...")
        for sql in DROP_STATEMENTS:
            table = sql.split()[-1]
            try:
                cursor.execute(sql)
                print(f"  ✓ DROP: {table}")
            except Exception:
                print(f"  — Yok (atlandı): {table}")

        # Oluştur
        print("\n[2/4] Tablolar oluşturuluyor...")
        for sql in CREATE_STATEMENTS:
            table = [w for w in sql.split() if w.isupper() and len(w) > 3][0]
            cursor.execute(sql)
            print(f"  ✓ CREATE TABLE: {table}")

        # Comment'ler
        print("\n[3/4] Comment'ler yazılıyor...")
        for sql in COMMENT_STATEMENTS:
            cursor.execute(sql)
        print(f"  ✓ {len(COMMENT_STATEMENTS)} comment yazıldı")

        # Örnek veri
        print("\n[4/4] Örnek veriler ekleniyor...")
        for sql in SAMPLE_DATA:
            cursor.execute(sql)
        conn.commit()
        print(f"  ✓ {len(SAMPLE_DATA)} satır eklendi")

    print("\n" + "=" * 55)
    print("✓ Şema hazır. Tablo özeti:")
    print("  DIM_CUSTOMER  — 5 müşteri")
    print("  DIM_PRODUCT   — 5 ürün")
    print("  DIM_DATE      — 5 tarih")
    print("  FACT_SALES    — 5 satış (FK tanımlı)")
    print("  FACT_RETURNS  — 2 iade  (FK YOK — implicit test)")
    print("\nTest komutu:")
    print("  python tests/test_server.py")
    print("=" * 55)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n✗ Hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)