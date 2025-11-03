# TestReportAnalyzer

## Proje Tanımı
TestReportAnalyzer, otomatik test raporlarını analiz ederek başarısız testlerin kök nedenlerini ve önerilen düzeltmeleri hızlıca ortaya çıkaran bir masaüstü/web hibrit uygulamasıdır. Uygulama PDF formatındaki test raporlarını alır, metin içeriklerini çözümler ve sonuçları kullanıcı dostu bir arayüzde sunar. Böylece QA ekipleri, başarısızlıkları incelemek için harcadıkları zamanı azaltır ve aksiyon alınması gereken alanları önceliklendirir.

## Özellikler
- PDF test raporlarının yüklenmesi ve metin tabanlı analiz edilmesi.
- PASS/FAIL sonuçlarının otomatik sayımı ve rapor özeti oluşturma.
- Her başarısız test için hata mesajı, olası neden ve önerilen çözümün çıkarılması.
- Raporların listelenmesi, sıralanması ve filtrelenmesi.
- Detay sayfasında test bazlı inceleme ve başarısız testlerin ayrı listelenmesi.
- Raporların sistemden silinebilmesi.

## Teknoloji Stack
- **Backend:** Python 3, Flask, SQLite, pdfplumber / PyPDF2, python-dateutil
- **Frontend:** React, React Router, Axios, React Scripts
- **Komut Dosyaları:** Windows PowerShell

## Gereksinimler
- Windows 10/11 üzerinde PowerShell 5.1 veya PowerShell 7+
- Python 3.11+
- Node.js 18+ ve npm
- PDF analizinde kullanılan kütüphaneler için temel C++ yapı araçları (gerekmesi halinde)

## Kurulum
Tüm adımlar PowerShell içerisinde uygulanmalıdır.

### 1. Depo klasörüne geçin
PowerShell penceresinde komutları çalıştırmadan önce proje klasörüne geçtiğinizden emin olun. Aksi halde `start-frontend.ps1`
gibi betikler "komut bulunamadı" hatası döndürebilir.

```powershell
cd C:\TestReportAnalyzer
```

### 2. (Gerekirse) Execution Policy kısıtlamasını kaldırın
Bazı Windows kurulumlarında varsayılan Execution Policy ayarı, depo içindeki PowerShell betiklerinin (ör. `setup.ps1`) çalış-
tırılmasını engelleyerek `running scripts is disabled on this system` hatasına yol açabilir. Komutların yalnızca mevcut oturum
için çalışmasına izin vermek üzere aşağıdaki komutlardan **birini** uygulayın:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

veya

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Bu yöntemler geçici olduğundan bilgisayarınızın genel güvenlik ayarlarını kalıcı olarak değiştirmez.

```powershell
# Depoyu klonlayın
git clone https://github.com/<kullanici-adiniz>/TestReportAnalyzer.git
cd TestReportAnalyzer

# Kurulum komut dosyasını çalıştırın
.\setup.ps1
```

> **Not:** PowerShell'de aynı klasördeki komut dosyalarını çalıştırmak için `.\` ön ekini kullanmanız önerilir. Bu sözdizimi 
> özellikle Windows PowerShell 5.1 gibi eski sürümlerde `./` kullanımının komutun bulunamamasına yol açmasını engeller.

`setup.ps1` betiği aşağıdaki işlemleri yapar:
1. Python ve Node.js kurulumlarını doğrular.
2. Backend için sanal ortam (`backend/venv`) oluşturur ve `requirements.txt` bağımlılıklarını yükler.
3. SQLite veritabanını başlatmak için `init_db()` fonksiyonunu çalıştırır.
4. Frontend bağımlılıklarını (`frontend` klasöründe) yükler.
5. PDF yüklemeleri için `backend/uploads/` klasörünü oluşturur.

> **Node.js Yüklü Değil mi?**
>
> Kurulum sırasında Node.js veya npm bulunamazsa betik backend kurulumuna devam eder ancak frontend bağımlılıkları adımını
> atlar. Bu durumda Node.js 18+ sürümünü yükledikten sonra `frontend` klasöründe `npm install` komutunu manuel olarak çalıştırmanız yeterlidir.

## AI Entegrasyonu (Opsiyonel)

Uygulama, test başarısızlıklarını analiz ederken **Claude** veya **ChatGPT** kullanabilir.

### Neden AI Kullanmalıyım?

**AI ile:**
- Daha akıllı ve spesifik hata analizi
- Bağlama uygun çözüm önerileri
- Karmaşık hataları anlama

**AI olmadan (Kural Tabanlı):**
- Ücretsiz
- Hızlı
- Internet bağlantısı gerektirmez
- Generic analiz

### API Key'leri Nasıl Alırım?

#### 1. Claude API Key (Önerilen)
1. https://console.anthropic.com adresine git
2. Hesap oluştur (ilk ay $5 ücretsiz credit)
3. "API Keys" bölümüne tıkla
4. "Create Key" butonuna bas
5. Key'i kopyala

#### 2. OpenAI API Key
1. https://platform.openai.com adresine git
2. Hesap oluştur
3. "API Keys" bölümüne git
4. "Create new secret key" butonuna bas
5. Key'i kopyala

### API Key'leri Nereye Yazmalıyım?
```powershell
# 1. Kurulumu yap (heniz yapmadıysan)
.\setup.ps1

# 2. .env dosyasını aç
notepad backend\.env

# 3. Key'leri yapıştır:
ANTHROPIC_API_KEY=sk-ant-api03-BURAYA_CLAUDE_KEYIN
OPENAI_API_KEY=sk-proj-BURAYA_OPENAI_KEYIN

# 4. AI Provider'ı seç (claude önerilir)
AI_PROVIDER=claude

# 5. Kaydet ve kapat
```

### AI Durumunu Kontrol Et
```powershell
.\check-ai.ps1
```

### AI Provider Seçenekleri

Backend\.env dosyasında `AI_PROVIDER` değişkeni:

- **`none`** (varsayılan): AI kullanma, kural tabanlı analiz yap (ücretsiz)
- **`claude`**: Sadece Claude kullan (önerilen, daha akıllı)
- **`chatgpt`**: Sadece ChatGPT kullan (daha ucuz)
- **`both`**: Önce Claude dene, başarısız olursa ChatGPT kullan

### backend/.env örneği

```ini
AI_PROVIDER=chatgpt
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
AI_OPENAI_MODEL=gpt-4o-mini
AI_ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
AI_MAX_TOKENS=1200
AI_TIMEOUT_S=60
```

> ⚠️ Bu dosya **depo dışında** tutulmalı; `.gitignore` üzerinden Git'e eklenmez.

### Sağlık ve API uçları

- `GET /api/health/ai` → Yapılandırmanın durumu (`has_openai`, `has_claude`, seçili modeller vb.).
- `POST /api/ai/analyze` → Gövde `{ "text": "..." }` ile AI özetini döndürür.
- `check-ai.ps1` → Yukarıdaki health endpoint'ini çağırarak sonucu JSON olarak yazar.

### Maliyet

- **Claude (Sonnet)**: ~$0.003 per analiz (~100 analiz = $0.30)
- **ChatGPT (GPT-4o-mini)**: ~$0.0001 per analiz (~100 analiz = $0.01)
- **Kural Tabanlı**: Ücretsiz

💡 **İpucu:** Başlangıçta `AI_PROVIDER=none` ile kullan, sonra istersen AI aktive et.

### Güvenlik

⚠️ **ÇOK ÖNEMLİ:**
- API key'lerin **GİZLİ BİLGİ**dir, kimseyle paylaşma
- `.env` dosyası GitHub'a yüklenmez (`.gitignore`'da)
- Key'leri public yerlere yazma
- Key'lerini düzenli rotate et

### Sorun Giderme

**Problem:** "AI Provider: Inactive" görünüyor
**Çözüm:** 
```powershell
.\check-ai.ps1  # Durum kontrol et
notepad backend\.env  # Key'leri kontrol et
```

**Problem:** "API Error" alıyorum
**Çözüm:**
- Key'in doğru kopyalandığından emin ol
- Key'in aktif olduğunu kontrol et (console'da)
- Internet bağlantını kontrol et
- AI_PROVIDER=none yap (geçici olarak)

## API KEY'LERİ NEREYE GÖMÜYORUZ? (DETAYLI AÇIKLAMA)

### 📁 Dosya Yapısı
```
TestReportAnalyzer/
├── backend/
│   ├── .env              ← API KEY'LER BURAYA (GİTHUB'A GİTMEZ!)
│   ├── .env.example      ← Örnek dosya (GitHub'a gider)
│   └── ...
└── .gitignore            ← .env dosyasını ignore eder
```

### 🔑 API Key'leri Koyma Adımları
1. İlk Kurulum
```powershell
# Setup çalıştır
.\setup.ps1

# Bu komut otomatik olarak .env.example'dan .env oluşturur
# backend/.env dosyası oluşmuştur ama içinde gerçek key yok
```

2. .env Dosyasını Aç
```powershell
notepad backend\.env
```

3. Key'leri Yapıştır
Dosya şöyle görünür:
```env
# AI API Keys - Kendi key'lerinizi buraya yazın
ANTHROPIC_API_KEY=your_claude_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

AI_PROVIDER=none
...
```

Şuna çevir:
```env
# AI API Keys - Kendi key'lerinizi buraya yazın
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

AI_PROVIDER=claude
...
```

#### 4. Kaydet ve Kapat
- Ctrl+S ile kaydet
- Dosyayı kapat

### 🛡️ Güvenlik - Nasıl Çalışıyor?

#### .gitignore Mekanizması
```
backend/.env        ← Bu dosya GitHub'a GİTMEZ (ignore edilir)
backend/.env.example ← Bu dosya GitHub'a GİDER (key'siz örnek)
```

### GitHub'da Görünenler
✅ GitHub'da görünür:

- .env.example (örnek, key yok)
- Tüm kod dosyaları
- README, scriptler

❌ GitHub'da görünmez:

- .env (gerçek key'ler burada)
- database.db
- uploads/*.pdf

### 🔄 Başka Bilgisayarda Kurulum
Senaryo: GitHub'dan projeyi başka bir bilgisayara klonladın.
```powershell
# 1. Clone yap
git clone https://github.com/username/TestReportAnalyzer.git
cd TestReportAnalyzer

# 2. Setup çalıştır (otomatik .env oluşturur)
.\setup.ps1

# 3. .env'e key'leri YENİDEN gir
notepad backend\.env
# Key'leri yapıştır

# 4. Çalıştır
.\start-app.ps1
```

### 📋 Kontrol Checklist
```powershell
# 1. .env dosyası var mı?
Test-Path backend\.env
# True dönmeli

# 2. .env içinde key'ler var mı?
notepad backend\.env
# Gerçek key'leri görmelisin (sk-ant-... veya sk-proj-...)

# 3. .env ignore ediliyor mu?
git status
# ".env" dosyası listede OLMAMALI

# 4. AI aktif mi?
.\check-ai.ps1
# ✓ işaretleri görmelisin
```

### ⚠️ YAPMAMANIZ GEREKENLER
❌ ASLA YAPMA:

- .env dosyasını git'e ekleme: `git add backend/.env` ← YAPMA!
- Key'leri README'ye yazma
- Key'leri kod dosyalarına hardcode etme
- Key'leri ekran görüntüsü alıp paylaşma
- .gitignore'dan .env satırını silme

✅ DOĞRU YAPILANLAR:

- .env sadece lokal bilgisayarında
- Key'ler sadece .env içinde
- .env.example GitHub'da (key'siz)
- Her bilgisayarda .env'i yeniden oluştur

### ÖZET KOMUTLAR (Sırayla Çalıştır)
```powershell
# 1. İlk kurulum
.\setup.ps1

# 2. Key'leri gir
notepad backend\.env
# Key'leri yapıştır, AI_PROVIDER=claude yap, kaydet

# 3. Kontrol et
.\check-ai.ps1

# 4. Başlat
.\start-app.ps1

# 5. Test et
# http://localhost:3000
```

## Çalıştırma
Uygulamayı başlatmak için kök dizinde aşağıdaki PowerShell komutunu çalıştırın:

```powershell
.\start-app.ps1
```

Betik, backend'i (Flask sunucusu) 127.0.0.1:5000 üzerinde, frontend'i ise 127.0.0.1:3000 üzerinde başlatır. Her iki hizmet yeni PowerShell pencerelerinde açılır ve durumu terminale yazdırılır.

Uygulamayı durdurmak için:

```powershell
.\stop-app.ps1
```

Alternatif olarak bileşenleri ayrı ayrı yönetmek isterseniz:

```powershell
.\start-backend.ps1   # Flask API'yi başlatır
.\start-frontend.ps1  # React uygulamasını başlatır
```

### Windows (PowerShell) notları

- PowerShell 5.1 kullanıyorsanız, konsol kod sayfasını ve I/O kodlamasını UTF-8 yapmanız önerilir.
- Frontend betiği `npm.ps1` yerine **npm.cmd** kullanacak şekilde güncellenmiştir.
- İlk kurulumda `npm ci` lock dosyası ile sürümler uyumsuzsa otomatik olarak `npm install` adımına düşer.
- Backend için `start-backend.ps1` venv yoksa otomatik **venv** oluşturur ve aktive eder.

> Not: `npm ci` sırasında `typescript` sürüm uyuşmazlığı (ör. lock 5.9.3 vs package.json 4.9.5) varsa,
> bir defaya mahsus `npm install` ile lock dosyasını güncelleyin veya `npm install typescript@<hedef-sürüm> --save-exact` uygulayın.

## Kullanım
1. Frontend arayüzünde "PDF Yükle" formunu kullanarak test raporunu yükleyin.
2. Yükleme tamamlandığında rapor listesine yeni bir kayıt eklenir.
3. Listeden bir rapora tıklayarak özet, PASS/FAIL sayıları ve başarısız test detaylarını görüntüleyin.
4. Başarısız testler için önerilen düzeltmeleri inceleyin veya raporu sistemden kaldırın.

## API Endpoints
| Metot | Endpoint | Açıklama |
|-------|----------|----------|
| `POST` | `/api/upload` | PDF raporunu yükler, analiz eder ve veritabanına kaydeder. |
| `GET` | `/api/reports` | Mevcut tüm raporları sıralama seçenekleriyle döndürür. |
| `GET` | `/api/reports/<id>` | Belirli bir raporun özet bilgilerini getirir. |
| `GET` | `/api/reports/<id>/failures` | Belirli raporun başarısız testlerini listeler. |
| `DELETE` | `/api/reports/<id>` | Raporu veritabanından siler ve ilişkili kayıtları temizler. |

Tüm yanıtlar JSON formatındadır ve CORS varsayılan olarak etkinleştirilmiştir.

## Proje Yapısı
```
TestReportAnalyzer/
├── backend/
│   ├── app.py
│   ├── database.py
│   ├── pdf_analyzer.py
│   ├── requirements.txt
│   └── models/
│       └── schema.sql
├── frontend/
│   ├── package.json
│   └── src/
│       ├── api.js
│       ├── App.js
│       ├── index.js
│       ├── styles/
│       │   └── App.css
│       └── components/
│           ├── Dashboard.js
│           ├── ReportDetail.js
│           ├── TestList.js
│           └── UploadForm.js
├── setup.ps1
├── start-app.ps1
├── start-backend.ps1
├── start-frontend.ps1
├── stop-app.ps1
└── test-samples/
    └── test_report_sample.pdf
```

## Lisans
Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.

## Sorun Giderme

### Problem: PDF yüklendi ama "test bulunamadı" hatası

**Neden:** PDF formatı sistem tarafından tanınmıyor olabilir.

**Çözüm Adımları:**

1. **PDF içeriğini kontrol et:**
```powershell
cd backend
.\check-pdf.ps1
# veya spesifik dosya için:
.\check-pdf.ps1 uploads\rapor.pdf
```

2. **Çıktıyı incele:**
   - "ANAHTAR KELİME ANALİZİ" bölümüne bak
   - Pass/Fail kelimeleri tespit ediliyor mu?
   - Tablo var mı, yoksa düz metin mi?

3. **Desteklenen Formatlar:**

**✅ Desteklenen:**
```
Test 1: Login
Durum: Başarılı

Test 2: Checkout
Durum: Başarısız
Hata: Timeout
```

**✅ Desteklenen (Tablo):**
```
Test Adı     | Sonuç      | Açıklama
Login Test   | Başarılı   | OK
API Test     | Başarısız  | Timeout
```

**❌ Desteklenmeyen:**
- Grafik/resim içinde gömülü test sonuçları
- Excel tabloları (PDF'e çevrilmeli)
- Çok karmaşık multi-column layout

4. **Özel Format Desteği:**

PDF'iniz farklı bir format kullanıyorsa, `backend/pdf_analyzer.py` dosyasındaki pattern'leri genişletmeniz gerekebilir.

### Problem: Türkçe karakterler bozuk görünüyor

**Çözüm:** Tüm dosyaların UTF-8 encoding ile kaydedildiğinden emin olun:
```powershell
# PowerShell'de:
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
```

### Problem: Test sayısı 0 ama PDF'de testler var

**Debug:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python test_parser.py
```

Eğer test parser çalışmıyorsa:
1. Pattern'leri kontrol et (pdf_analyzer.py)
2. PDF text extraction kontrolü yap (test_pdf_debug.py)
3. Log dosyalarına bak (backend çalışırken console output)

## Sorun Giderme: Analiz Boş Geliyor

### Problem: Test Koşulları ve Grafikler boş

**Teşhis adımları:**

1. **Backend log'larını kontrol et:**
```powershell
# Backend çalışırken console'u izle
# "KAPSAMLI PDF ANALİZİ" log'larını ara
```

2. **Manuel test:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python test_full_analysis.py uploads/dosya.pdf
```

**Beklenen çıktı:**
```
✓ Test koşulları OK (200+ karakter)
✓ Grafik analizi OK (150+ karakter)
```

3. **AI çalışıyor mu kontrol:**
```powershell
.\check-ai.ps1
# "ok": true görmeli
```

4. **Bölüm tanıma çalışıyor mu:**
Backend log'larında şunu ara:
```
ADIM 3: Bölüm Tanıma
  ✓ Tespit edilen bölüm sayısı: 3+
```

Eğer "0" ise: PDF formatı tanınmıyor.

### Çözümler:

**Durum 1: Bölüm sayısı 0**
→ PDF formatı beklenenden farklı
→ `pdf_section_analyzer.py` pattern'lerini genişlet

**Durum 2: AI yanıt vermiyor**
→ API key kontrol et: `.\check-ai.ps1`
→ .env dosyasında doğru key var mı?

**Durum 3: Backend hata veriyor**
→ Console'daki stack trace'i incele
→ Module eksik mi? `pip install -r requirements.txt`

ÖZET CHECKLIST
Backend:

 pdf_analyzer.py - Detaylı log ekle
 pdf_section_analyzer.py - detect_sections güçlendir
 ai_analyzer.py - analyze_test_conditions düzelt
 ai_analyzer.py - analyze_graphs düzelt
 ai_analyzer.py - _call_claude_for_analysis ekle
 ai_analyzer.py - _call_openai_for_analysis ekle
 ai_analyzer.py - _extract_basic_info ekle
 ai_analyzer.py - _extract_graph_info ekle
 routes.py - Database kayıt log ekle
 test_full_analysis.py - Test scripti ekle

Frontend:

 ReportDetail.js - Debug bilgisi ekle
 ReportDetail.js - Console.log ekle

Dokümantasyon:

 README.md - Troubleshooting bölümü

Test:
```powershell
# 1. Full analysis test
cd backend
python test_full_analysis.py

# 2. Backend başlat (log'ları izle)
python app.py

# 3. Frontend'den PDF yükle

# 4. Console'da şunları ara:
# - "ADIM 3: Bölüm Tanıma" → Sayı > 0 olmalı
# - "ADIM 6: AI Analizi" → Hata olmamalı
# - "Test koşulları analiz edildi" → Karakter sayısı > 100
# - "Grafikler analiz edildi" → Karakter sayısı > 100
```
