# Windows Kurulumu: PyMuPDF ve Tesseract Hatalarını Giderme

Bu doküman, Windows 10/11 üzerinde `pip install pymupdf==1.24.5` sırasında Visual Studio hatası alınması ve `tesseract --version` komutunun tanınmaması durumlarında izlenmesi gereken adımları özetler.

## 1. PyMuPDF Kurulumu İçin Visual Studio Build Tools

Python 3.13 için PyMuPDF önceden derlenmiş wheel yayınlamadığından, paket kurulumu sırasında MuPDF çekirdeği kaynak koddan derlenir. Bu işlem aşağıdaki bileşenlere ihtiyaç duyar:

- **Microsoft Visual C++ Build Tools (MSVC)**
- **Windows 10/11 SDK**

### 1.1 Visual Studio Build Tools'u Yükleme

1. [Visual Studio Downloads](https://visualstudio.microsoft.com/downloads/) sayfasını açın.
2. "**Tools for Visual Studio**" bölümünde **"Build Tools for Visual Studio"** indirme düğmesine tıklayın.
3. Kurulum programını çalıştırdığınızda "**Desktop development with C++**" iş yükünü seçin.
   - Sağ paneldeki **MSVC v143 - VS 2022 C++ x64/x86 build tools** ve **Windows 10/11 SDK** bileşenlerinin işaretli olduğundan emin olun.
4. İndir & yükle butonuna tıklayın ve kurulumun tamamlanmasını bekleyin.
5. Kurulum bittikten sonra bilgisayarı yeniden başlatmanız önerilir.

### 1.2 Kurulumu Doğrulama

> Bu adımlar, `Unable to find Visual Studio` hatasına neden olan C++ derleyicisinin yolunu doğrular.

1. **Developer PowerShell for VS 2022** kısayolunu açın.
2. Aşağıdaki komutla MSVC ortam değişkenlerinin yüklendiğini doğrulayın:
   ```powershell
   cl
   ```
   Eğer kurulum başarılıysa komut derleyici sürümünü yazdırır; aksi halde "'cl' is not recognized" hatası alırsınız.
3. Visual Studio kurulumlarını listelemek için `vswhere` aracını çalıştırın:
   ```powershell
   vswhere -latest -requires Microsoft.Component.MSBuild
   ```
   Bu komut, kurulu sürümün yolunu (`installationPath`) göstermelidir.

### 1.3 PyMuPDF'ü Yeniden Kurma

1. Aynı **Developer PowerShell** penceresinde proje klasörünü açın:
   ```powershell
   cd C:\TestReportAnalyzer
   ```
2. Sanal ortam kullanıyorsanız etkinleştirin (opsiyonel):
   ```powershell
   .\backend\venv\Scripts\Activate.ps1
   ```
3. Kurulumu yeniden deneyin:
   ```powershell
   pip install pymupdf==1.24.5
   ```

> **Alternatif:** Eğer derleme süreci çok uzun sürüyor veya hata almaya devam ediyorsanız, Python 3.12 ile ayrı bir sanal ortam oluşturup PyMuPDF'ün hazır wheel dosyasından kurulmasını sağlayabilirsiniz:
>
> ```powershell
> py -3.12 -m venv C:\venvs\tra-py312
> C:\venvs\tra-py312\Scripts\Activate.ps1
> pip install --upgrade pip
> pip install pymupdf==1.24.5
> ```
> 
> Daha sonra proje bağımlılıklarını bu ortamdan yönetebilirsiniz.

## 2. Tesseract OCR'ı PATH'e Eklemek

`pytesseract` modülü, sistem PATH'inde `tesseract.exe` bulunmadığında "komut bulunamadı" hatası verir. Çözüm için aşağıdaki adımları izleyin.

### 2.1 Tesseract'ı Yükleme

1. [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) sayfasından Windows için en güncel `.exe` kurulum dosyasını indirin.
2. Kurulum sırasında şu seçenekleri işaretlediğinizden emin olun:
   - **Additional language data** (ihtiyaç duyulan diller)
   - **Add to PATH** (sistemin komutu tanıyabilmesi için zorunludur)
3. Kurulum tamamlandığında yeni bir PowerShell penceresi açın.

### 2.2 PATH'i Doğrulama

1. `tesseract --version` komutunu çalıştırın:
   ```powershell
   tesseract --version
   ```
   Çıktıda Tesseract sürümü görünmelidir. Eğer hâlâ "tanınmıyor" hatası alıyorsanız PATH değişkeni güncellenmemiş olabilir.
2. Tesseract'ın kurulu olduğu klasörü kontrol edin. Varsayılan yol genellikle:
   ```
   C:\Program Files\Tesseract-OCR\tesseract.exe
   ```
3. Bu yol listelenmiyorsa, geçici olarak aşağıdaki komutla mevcut oturuma ekleyebilirsiniz:
   ```powershell
   $env:PATH += ";C:\Program Files\Tesseract-OCR"
   ```
   Kalıcı ekleme için Windows "Sistem Ortam Değişkenleri" arayüzünden PATH'e aynı değeri ekleyin.

### 2.3 Proje Yapılandırması

Tesseract farklı bir konuma kurulmuşsa veya PATH'e eklemek istemiyorsanız, backend `.env` dosyasında tam yolu belirtin:

```ini
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## 3. Yaygın Sorunlar

| Sorun | Muhtemel Sebep | Çözüm |
| --- | --- | --- |
| `Unable to find Visual Studio` | MSVC Build Tools yüklü değil veya kurulum yolu 2022 klasör yapısıyla eşleşmiyor | Build Tools'u yeniden yükleyin; `vswhere` çıktısının `C:\Program Files\Microsoft Visual Studio\2022\BuildTools` içerdiğini doğrulayın |
| `cl is not recognized` | Geliştirici kabuğu kullanılmıyor veya PATH güncellenmedi | "Developer PowerShell for VS 2022" açın veya `vcvarsall.bat` betiğini manuel çalıştırın |
| `tesseract: ... is not recognized` | Tesseract kurulmadı veya PATH güncellenmedi | UB Mannheim kurulumunu çalıştırın ve "Add to PATH" seçeneğini seçin; gerekirse PATH'e elle ekleyin |
| OCR sırasında `TesseractNotFoundError` | `TESSERACT_CMD` ortam değişkeni yanlış | `.env` dosyasındaki yolu doğrulayın, ters eğik çizgileri `\` olarak kaçış yapın |

## 4. Kontrol Listesi

- [ ] Visual Studio Build Tools yüklendi ve `cl` komutu çalışıyor.
- [ ] `pip install pymupdf==1.24.5` komutu hata vermeden tamamlanıyor.
- [ ] Tesseract OCR kurulumu ardından `tesseract --version` çıkışı doğrulandı.
- [ ] Gerekirse `.env` dosyasında `TESSERACT_CMD` güncellendi.

Bu adımları tamamladıktan sonra `setup.ps1` ve diğer PowerShell betiklerini çalıştırarak projeyi normal şekilde kullanabilirsiniz.
