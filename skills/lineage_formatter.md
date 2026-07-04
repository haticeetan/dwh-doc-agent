# Bağımlılık Açıklama Talimatı

Tablo ilişkilerini belgelerken aşağıdaki kuralları uygula:

## FK İlişkileri (Doğrulanmış)
- "X kolonu, Y tablosunun Z kolonuna foreign key ile bağlıdır." formatını kullan
- İlişkinin iş anlamını açıkla: "Her satış kaydı mutlaka bir müşteriye ait olmak zorundadır."

## Örtük İlişkiler (Doğrulanmamış)
- Mutlaka "(doğrulanmamış)" notunu ekle
- "X kolonu muhtemelen Y tablosuna referans vermektedir, ancak FK constraint tanımlı değildir." yaz
- Güven seviyesini belirt: high → "büyük ihtimalle", medium → "muhtemelen"

## Yönlü İlişkiler
- Bu tablo başka tablolara bağımlıysa: "Bu tablo ... tablosuna bağımlıdır."
- Başka tablolar bu tabloya bağımlıysa: "... tablosu bu tabloyu referans almaktadır."

## Kullanılan Nesneler
- View veya prosedür bu tabloyu kullanıyorsa mutlaka belirt
- "X view'i bu tablodan beslenmektedir." formatını kullan

## Dikkat
- Hiç ilişki yoksa "Bu tablonun diğer tablolarla tanımlı bir ilişkisi bulunmamaktadır." yaz
- Asla olmayan bir ilişki uydurma