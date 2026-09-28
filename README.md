# Mühür Kontrol

Bir klasördeki PDF belgelerinde referans mühür arayan, Windows 10/11 öncelikli masaüstü uygulaması. **Mühür bulundu eşiğine ulaşan ilk geometrik doğrulanmış eşleşmede o PDF’nin taraması tamamlanır ve sonraki PDF’ye geçilir.** Eşiğe ulaşılmazsa tüm sayfalar taranır. PySide6, OpenCV SIFT ve PyMuPDF kullanır. Model, eğitim, yapay zekâ API’si, sunucu, hesap veya veritabanı yoktur. Çalışırken internet gerekmez; PDF ve görseller dışarı gönderilmez. İlk paket kurulumu internet gerektirebilir.

## Hızlı başlangıç

64 bit Python 3.11 veya 3.12 önerilir. Depoyu klonlayın veya kaynak ZIP'ini bir klasöre açın. Python kurulurken komut satırına ekleme seçeneğini açın. Proje klasöründe:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Kurulumdan sonra Windows'ta **`baslat.bat` dosyasına çift tıklayarak** da başlatabilirsiniz. `.venv` depoya dahil değildir; her bilgisayarda yeniden oluşturulur.

İsterseniz mevcut Python ortamınıza doğrudan kurabilirsiniz:

```powershell
pip install -r requirements.txt
python main.py
```

Linux/macOS üzerinde de kaynak kod kullanılabilir; sanal ortam yorumlayıcısının yolu `.venv/bin/python` olur. Bu teslimde Windows ortamı test edilmiştir.

## Kullanım

1. **+ Ekle** ile PNG/JPG/JPEG/BMP referans mühürlerinizi seçin. Özellikler bir kez arka planda hesaplanır. Önizleme ve özellik sayısı gösterilir. Aynı dosya yeniden eklenmez.
2. PDF klasörünü seçin. Alt klasörler varsayılan olarak dahildir; seçeneği kapatabilirsiniz. Büyük/küçük harfli `.pdf` uzantıları desteklenir.
3. Varsayılan 200 DPI, mühür bulundu eşiği 80 ve manuel kontrol eşiği 50 ile **Taramayı başlat** düğmesine basın.
4. Dosya sayısı, ilerleme, mevcut dosya ve tek işlem modunda sayfa ilerlemesini takip edin. Tarama sırasında sonuçlar eklenir; arayüz kullanılabilir kalır.
5. **En düşük skor önce** ve **Sadece kontrol gerekenler** ile şüpheli belgeleri öne alın. Hatalı ve iptal edilmiş belgeler de kontrol gerekenler arasındadır. Durum filtresi ile kontrol seçeneği birlikte uygulanır.
6. Bir satıra çift tıklayın veya **İncele** düğmesine basın. Kaydedilen eşleşmenin sayfası açılır; diğer sayfalara da geçilebilir. Geometrik doğrulanmış bölge renkli dörtgenle gösterilir. `+`, `−` veya Ctrl + fare tekerleği ile yakınlaştırın, sürükleyerek gezin.
7. **PDF’yi aç** belgenin işletim sistemindeki varsayılan okuyucusunu açar.
8. **CSV dışarı aktar**, filtreye bakmaksızın o ana kadar alınan **tüm sonuçları** kaydeder. UTF-8 BOM, noktalı virgül ayırıcı ve noktalı ondalık kullanılır. Türkçe karakterler korunur; formül gibi başlayan metin hücreleri güvenli hale getirilir. Excel zorunlu değildir.

Sonuçlar yalnızca bellekte tutulur; uygulamayı kapatmadan önce raporu kaydedin. Yeni tarama mevcut sonuçları değiştirir. Son PDF klasörü yerel QSettings içinde hatırlanır. Referanslar ve diğer ayarlar uygulama kapandığında sıfırlanır.

**Taramayı durdur** yeni işlerin başlatılmasını keser. Devam eden OpenCV/render çağrısı bitince iptal uygulanır; zorla süreç sonlandırılmaz. Kısmen taranmış belgeler “İptal edildi” olarak işaretlenir, “Mühür bulundu” sayılmaz. Başlanmamış dosyalar için sonuç satırı üretilmez. İşlem sürerken pencere kapatılırsa güvenli durdurma tamamlanınca kapanır.

## Referans mühür hazırlama

- Yalnızca mühür alanını kırpın; çevredeki yazı ve geniş beyaz boşlukları kaldırın.
- Net ve yeterince yüksek çözünürlüklü görüntü kullanın; mühür detayları görünür olmalı.
- Farklı baskı yoğunluklarından ve farklı taramalardan birkaç örnek ekleyin.
- Soluk veya yazıyla örtüşen mühürler için benzer koşullardaki ek referanslar yararlıdır.
- Şeffaf görseller beyaz zeminle birleştirilir. 16 bit görseller 8 bite dönüştürülür.
- Çok büyük referanslar en uzun kenarı 1600 piksel olacak şekilde küçültülür.
- En az 8 ayırt edici SIFT özelliği olmayan görseller açıklayıcı mesajla reddedilir.
- Aynı isimli farklı klasörlerdeki referanslara ayırt edici dosya adları verin; raporda referansın dosya adı kullanılır.

## Eşleşme yöntemi ve skorlar

Her PDF sayfası doğrudan RGB görüntüye render edilir; yalnızca gömülü resimler çıkarılmaz. İşlem hattı:

1. Gri tonlama, hafif Gaussian filtre, CLAHE kontrast iyileştirmesi.
2. Referans için en çok 3000, sayfa için en çok 12000 SIFT özelliği.
3. BFMatcher L2, KNN `k=2`, Lowe oran testi (varsayılan 0,70).
4. Aynı sayfa özelliğine birden fazla oy verilmesini önleyen eşleşme tekilleştirmesi.
5. En az 8 iyi eşleşmeyle RANSAC homografisi (varsayılan 5 piksel tolerans).
6. En az 8 inlier, en az 0,40 inlier oranı, referans alanının en az %8’ine yayılan destek.
7. Sonlu, dışbükey, aynalanmamış dörtgen; sayfa sınırları, alan, kenar oranları, perspektif ufku ve yeniden izdüşüm hatasının kontrolü.
8. Referanslar ve sayfalar sırayla değerlendirilir. Skor **mühür bulundu eşiğine eşit veya yüksekse** ve geometri geçerliyse kalan referanslar/sayfalar atlanır; o eşleşme kaydedilir. Örneğin eşik 80 ise 80 puanlık doğrulanmış eşleşme yeterlidir. Eşiğe ulaşılmazsa tüm sayfalardaki en iyi aday saklanır. Erken tamamlanan PDF iptal edilmiş sayılmaz; önceden yaşanan sayfa hataları varsa hata durumu korunur.

Erken tamamlamada sonuç, belgenin mutlak en yüksek skoru değil, **eşiği sağlayan ilk eşleşmedir**. İnceleme ekranı ve CSV’de taranan/toplam sayfa sayısı korunur; taranmayan sayfalar önizlemede yine açılabilir.

**Benzerlik skoru gerçek bir istatistiksel olasılık değildir. Görüntü eşleşme algoritmalarından üretilen karşılaştırmalı bir güven skorudur.**

Geometrik doğrulanan adayların skoru; özellik desteği (%15 ağırlık), inlier oranı (%25), inlier sayısı (%20), referanstaki alan kapsamı (%20), descriptor mesafesi (%10) ve yeniden izdüşüm hassasiyetinin (%10) birleşimidir. Formül `app/processing/scoring.py` dosyasında ayrı tutulur. Doğrulanmayan adaylar düşük skorla sınırlandırılır ve kullanıcı eşiği düşürse bile “Mühür bulundu” sınıfına alınmaz.

| Varsayılan skor | Sonuç |
| --- | --- |
| 80–100 ve geçerli geometri | Mühür bulundu |
| 50–80 arası, 80 hariç | Manuel kontrol |
| 0–50 arası, 50 hariç | Mühür bulunamadı |
| Dosya/sayfa işleme hatası | İşleme hatası |
| Tamamlanmadan durdurulan belge | İptal edildi |

“Mühür bulunamadı” mühürün kesinlikle olmadığı anlamına gelmez. Düşük kalite veya yetersiz referans yüzünden tespit kaçabilir. Skor sıfırsa en iyi sayfa/referans boş kalabilir; inceleme penceresi ilk sayfayı açar. Bir sayfa hatası olsa bile diğer sayfalar işlenir; sonuç hatalı olarak kalır ve elde edilen en iyi aday inceleme için korunur.

## Ayarlar ve performans

İşlem adımları ve hız seçenekleri için [performans açıklamasını](PERFORMANS_README.md) okuyun.

- **DPI:** 150 / 200 / 250 / 300. Varsayılan 200. Daha yüksek değer daha çok zaman ve bellek kullanır.
- **Eşikler:** `0 < manuel kontrol < mühür bulundu ≤ 100` zorunludur. Sonuçlar tarama başlangıcındaki ayarlarla üretilir; yeni eşikler için yeniden tarayın.
- **Lowe oranı:** 0,40–0,90. Artırmak daha çok aday ve yanlış eşleşme getirebilir.
- **RANSAC toleransı:** 1–15 render pikseli. Büyük değer daha fazla geometrik sapmaya izin verir.
- **Paralel işlem:** 1 (varsayılan), 2, 4, 8, Otomatik. Otomatik en çok 2 süreç seçer. 4/8 işlemi ancak yeterli RAM ile kullanın; büyük belgelerde birkaç GB bellek gerekebilir.
- **Renk ön filtresi:** Kapalı / Kırmızı / Mavi. HSV maskesi ve genişletme kullanır. Açıkken SIFT özelliklerini seçili renk çevresiyle sınırlar; siyah-beyaz veya çok soluk mühürleri kaçırabilir. Varsayılan kapalıdır.

Her işlemde yalnızca mevcut PDF sayfasının görüntüsü tutulur. Paralel iş kuyruğu işlem sayısıyla sınırlıdır; tüm PDF’ler RAM’e yüklenmez. Referans özellikleri süreç başına bir kez aktarılır. OpenCV dahili iş parçacığı sayısı 1 ile sınırlanır. PyMuPDF işlemleri aynı süreçte kilitle seri hale getirilir; paralel tarama ayrı süreçlerde yürür. Aşırı büyük sayfalarda bellek koruması için render en fazla yaklaşık 20 milyon piksel ve 6000 piksel kenarla sınırlanır; tüm sayfa yine işlenir, fiili DPI azalabilir.

## Hata yönetimi ve kayıtlar

Bozuk, şifreli veya okunamayan PDF’ler, render ve OpenCV hataları diğer belgelerin taranmasını durdurmaz. Boş veya özelliksiz sayfalar geçerli eşleşmesiz sayfa sayılır. Şifreli PDF için uygulama parola sormaz; şifresiz kopya gerekir.

`logs/app.log` uygulama açılışını, referansları, taramaları, dosya sürelerini ve hataları kaydeder. Kayıtlar 2 MB’da döner; en çok 3 eski dosya tutulur. Proje klasörüne yazılamıyorsa kullanıcı profilindeki `StampChecker/logs` kullanılır. Kayıtlar yerel dosya yolları içerebilir.

CSV’de dosya yolu, kaydedilen sayfa/referans/skor/durum, süre, eşleşme sayısı, inlier oranı, kutu, dörtgen, render boyutu, işlenen/toplam sayfa ve hata metni bulunur. Dörtgen/kutu koordinatları kaydedilen render boyutundaki piksel koordinatlarıdır; PDF nokta koordinatı değildir. İnceleme görünümünde yeniden render boyutuna ölçeklenir.

## Testler

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testler geçici klasörde sentetik referans ve PDF üretir. Tek/çok sayfalı belgeler, dönüş/ölçek farkı, çoklu referans, boş referans/klasör, özelliksiz görsel, şeffaflık, bozuk/şifreli PDF, iptal, geometrik koruma, CSV, sayısal sıralama, filtreler, pencere açılışı, arka plan çoklu süreç taraması ve önizleme kontrol edilir. GUI testleri görünmez Qt platformunda çalışır. Gerçek referanslarla doğruluk yüzdesi ölçülmemiştir.

## Bilinen sınırlamalar

- Bu yöntem mühürün orijinalliğini veya hukuki geçerliliğini doğrulamaz; görsel benzerlik arar.
- Çok küçük, soluk, örtülmüş, ciddi bozulmuş veya az detaylı mühürler kaçabilir. Benzer yazı ve şekiller yanlış pozitif üretebilir; geometrik kontroller riski azaltır, ortadan kaldırmaz.
- Bütün sayfa SIFT özellik sayısı sınırı, çok yoğun belgelerde küçük mühürlerin özelliklerini dışarıda bırakabilir.
- Dönme/ölçek/perspektif değişimlerine dayanıklılık vardır; her belge için garanti yoktur. Otomatik tarama sonuçlarını kendi olumlu/olumsuz örneklerinizle değerlendirin.
- Minimum destek/alan/geometri kontrolleri korumacıdır; küçük bir parçası görünen mühürler otomatik onay almayabilir.
- İptal, devam eden tek bir yerel render veya SIFT çağrısını ortasında kesmez. Çok büyük/problemli bir sayfada bekleme uzayabilir.
- PDF klasöründeki dosyaların tarama sırasında değiştirilmemesi önerilir. Önizleme dosyanın o andaki içeriğini gösterir.
- OCR, mühür türü sınıflandırması, oturum veritabanı, işaretli PDF kaydetme ve model tabanlı tespit içermez.

## Proje yapısı

```text
main.py                     Uygulama girişi
baslat.bat                  Windows başlatıcısı
requirements.txt            Kullanılan paketler
app/
  gui/                      Ana pencere, sonuç modeli/filtre, sayfa inceleyici
  models/                   Referans, eşleşme ve belge sonuç veri sınıfları
  processing/               Render, ön işleme, SIFT, geometri, skor, tarayıcı
  workers/                  Arka plan referans yükleme ve seri/paralel tarama
  utils/                    Ayar doğrulama, dönen log, CSV raporu
tests/                      Sentetik veri ve otomatik testler
tools/package_source.py     Kullanıcı verileri olmadan kaynak ZIP'i oluşturur
.github/workflows/tests.yml Windows otomatik test akışı
logs/                       İlk çalıştırmada oluşan yerel kayıtlar
```

## GitHub ve kaynak paketi

[GitHub yükleme kılavuzu](GITHUB_YUKLEME.md), paylaşılacak dosyaları ve yükleme adımlarını açıklar. `.gitignore` sanal ortamı, logları, raporları ve kullanıcı belgelerini kapsam dışında tutar. Kaynak arşivi `python tools/package_source.py` ile oluşturulur.

Windows üzerinde Python 3.11 ve 3.12 için GitHub Actions test akışı bulunur. Proje için henüz dağıtım lisansı seçilmemiştir.
