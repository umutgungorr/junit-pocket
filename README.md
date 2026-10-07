# JUnit Pocket

JUnit XML raporunu küçük, makine tarafından okunabilir bir JSON özetine dönüştüren yerel Python CLI.
CI sonuçlarını incelemek veya başka bir araca aktarmak için gerçek test sayılarını ve
başarısız testlerin adlarını çıkarır. Hesap, API anahtarı veya çalışma zamanı bağımlılığı istemez.

GitHub Actions, her push ve PR'da testleri ve Ruff kontrollerini çalıştırır.

## Hızlı kullanım

Python **3.12 veya üzeri** gerekir. Bu klasördeki kaynak kodla doğrudan çalıştırabilirsiniz.

PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
python -m junit_pocket --junit examples/sample.xml
python -m junit_pocket --junit examples/sample.xml --max-items 5 -o report.json
```

Linux / macOS:

```bash
PYTHONPATH=src python -m junit_pocket --junit examples/sample.xml
PYTHONPATH=src python -m junit_pocket --junit examples/sample.xml --max-items 5 -o report.json
```

Kendi raporunuz için `examples/sample.xml` yerine JUnit XML dosyanızı verin.
`-o` kullanmazsanız JSON stdout'a yazılır. Çıktı dosyası varsa işlem reddedilir;
aynı isimdeki dosyayı ezmez. Rapor test hatası içerse de başarılı dönüşümün çıkış kodu `0` olur.
Geçersiz argüman, girdi veya çıktı hatasında çıkış kodu `2` olur.

## Örnek çıktı

Bir başarılı, bir atlanan, bir başarısız ve bir kurulum hatası olan örnek rapor:

```json
{
  "schema_version": "1.0",
  "summary": {"tests": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1},
  "failures": [
    {"kind": "failure", "name": "test_checkout", "classname": "tests.shop"},
    {"kind": "error", "name": "test_connection", "classname": "tests.db"}
  ],
  "omitted_failures": 0,
  "notice": "Best effort masking; identifiers may still contain sensitive data."
}
```

Test sayıları XML'in özet sayaçlarından değil, gerçek `testcase` kayıtlarından hesaplanır.
`error`, `failure` ve `skipped` aynı kayıtta bulunursa öncelik bu sıradadır.
XML namespace'leri, iç içe suite'ler ve UTF-8 BOM desteklenir. Boş suite sıfır sonuç üretir;
test sayısı pozitif ilan edilmiş ama kayıt içermeyen rapor reddedilir.

## Seçenekler

| Seçenek | Davranış |
| --- | --- |
| `--junit DOSYA` | Zorunlu JUnit XML girdisi |
| `-o DOSYA`, `--output DOSYA` | Yeni dosyaya JSON yaz; varsayılan stdout |
| `--max-items SAYI` | İlk 1–100 hata kaydını göster; varsayılan 20 |
| `--help` | Yardım metni |

`omitted_failures`, liste sınırı nedeniyle gösterilmeyen failure/error kayıtlarını sayar.
Her ad ve sınıf adı en fazla 160 karakterdir. JSON biçimi `schema_version: "1.0"` ile sürümlenir.

## Veri ve sınırlar

- Girdi en fazla **1 MiB**, UTF-8 veya UTF-8 BOM içeren normal bir dosya olmalıdır.
- Girdi symlink'leri, XML DOCTYPE/ENTITY, yanlış kök ve geçersiz XML reddedilir.
- Kaynak kod, testler veya ağ çağrıları çalıştırılmaz; girdi dosyası değiştirilmez.
- Failure mesajları, stack trace, dosya yolları ve yakalanmış stdout/stderr dışarı verilmez.
- Ad/sınıf alanlarında `API_KEY=...`, `Bearer ...` ve `ghp_...` desenleri kısaltmadan önce
  `[REDACTED]` ile maskelenir. Bu **best effort** işlemdir: diğer hassas değerler isimlerde kalabilir.
- Ruff, Markdown, otomatik hata teşhisi ve tam anonimleştirme bu sürümün kapsamında değildir.

## Doğrulama

Ürün, ağ erişimi kapalı ve normal kullanıcıyla çalışan Docker ortamında
sözdizimi, Ruff, korunan CLI sözleşmesi, davranış/regresyon testleri ve CLI smoke aşamalarından geçer.
Kabul testleri ile ek regresyonlar `tests/` altında bulunur.

Geliştirme ortamında pytest kuruluysa testleri çalıştırmak için:

```powershell
$env:PYTHONPATH = (Resolve-Path ./src).Path
python -m pytest -q
```

Kaynak üzerinden kullanım doğrulanmıştır. PyPI yayını veya wheel kurulumu bu teslimin kapsamında değildir.

## Üretim kaydı

İlk taslak Daily PR Factory tarafından **bir Gemini çağrısıyla** oluşturuldu ve davranış
kontrollerinin bir kısmında başarısız oldu. Bu teslimde kod **Codex tarafından yerel olarak
düzeltilmiş**, belgelenmiş ve yeniden Docker'da doğrulanmıştır; ek Gemini çağrısı yapılmadı.
Bu sürüm tamamen otonom Gemini üretimi başarısı olarak sunulmaz.
Ürünün pazar talebi veya rakiplerden farklılaşması henüz doğrulanmış değildir.

JUnit rapor biçimi bağlamı: [pytest JUnit XML çıktısı](https://docs.pytest.org/en/stable/how-to/output.html).
