# Dokümantasyon Format Talimatı

Tablo dokümantasyonunu aşağıdaki yapıda oluştur:

## [TABLO_ADI]

### Genel Açıklama
Tablonun ne işe yaradığını, veri ambarındaki rolünü ve hangi iş sürecini temsil ettiğini 2-3 cümleyle açıkla.

### Kolonlar

| Kolon Adı | Veri Tipi | Zorunlu | Açıklama |
|-----------|-----------|---------|----------|
| ... | ... | ... | ... |

Her kolon için kısa ve anlamlı bir açıklama yaz. Özellikle:
- _ID ile biten kolonlar için ne tür bir kimlik olduğunu belirt
- _DATE, _TS ile biten kolonlar için hangi olayın tarihini tuttuğunu belirt
- FLAG, IND, IS_ ile başlayan kolonlar için 0/1 değerlerinin ne anlama geldiğini yaz
- AMOUNT, PRICE, COST kolonları için para birimi ve ölçek bilgisini ekle

### İlişkiler

Bu bölümü YALNIZCA prompt'ta "Bu İstekteki Tablolarla İlişkiler" başlıklı bir bölüm varsa yaz.
O bölüm yoksa İlişkiler kısmını hiç ekleme.

Bölüm varsa sadece orada listelenen ilişkileri kullan:
- "Onaylanmış ilişkiler" altındakileri kesin olguymuş gibi sun: "{kolon} → {hedef_tablo}.{hedef_kolon}" formatında
- "Olası ilişkiler" altındakileri "olabilir", "muhtemelen" gibi ifadelerle yaz — kesin gerçekmiş gibi sunma
- Bu iki grubu dokümanda açıkça ayırt et

### Örnek Kullanım

Bu tabloyla sık kullanılan bir sorgu veya iş kuralı örneği ver.

### Notlar

Dikkat edilmesi gereken özel durumlar, bilinen veri kalitesi sorunları veya iş kuralları varsa buraya yaz.