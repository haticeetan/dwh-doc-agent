# Dokümantasyon Kalite Değerlendirme Talimatı

Senden bir tablo dokümantasyonunu değerlendirmeni istiyorum.
Aşağıdaki kriterlere göre 0.00 ile 1.00 arasında bir puan ver.

## Puanlama Kriterleri

### 1. Kolon Kapsamı (0.4 ağırlık)
- Tüm kolonların açıklaması varsa tam puan
- Her eksik kolon açıklaması için puan düş
- Yüzeysel "bu bir ID kolonudur" gibi açıklamalar yarım puan sayılır

### 2. İlişki Açıklaması (0.3 ağırlık)
- FK ilişkileri belirtilmişse tam puan
- Örtük ilişkiler "(doğrulanmamış)" notu ile yazılmışsa tam puan
- İlişki hiç yoksa bu kriter geçer

### 3. Genel Tablo Amacı (0.3 ağırlık)
- Tablonun veri ambarındaki rolü açıklanmışsa tam puan
- Sadece teknik bilgi verilip iş amacı yazılmamışsa yarım puan

## Örnekler

- Tüm kolonlar açıklanmış, ilişkiler belirtilmiş, amaç yazılmış → 0.95
- Kolonların yarısı açıklanmış, ilişkiler var, amaç yazılmış → 0.75
- Kolonlar yüzeysel, ilişkiler eksik → 0.50
- Sadece kolon listesi var, açıklama yok → 0.20

Sadece sayısal değer yaz. Başka hiçbir şey ekleme.