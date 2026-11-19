# Öğretmen–Öğrenci Simülasyonu

GSM8K (EN) + GSM8K-TR socratic sorularından, aynı LLM'in öğretmen (düşünme açık) ve öğrenci (düşünme
kapalı, JSON) rollerinde konuştuğu Türkçe diyaloglar üretir. Her turu deterministik bir Python hakemi
denetler; geçmeyen tur yeniden üretilir. Çıktı: SFT verisi (sistem istemi yok, iz + Türkçe cevap) ve
DPO aday çiftleri.

Talimat: `../betik_talimatı.md`.

## Kurulum

```bash
cd simulasyon
uv venv --python 3.12 .venv            # ya da: python -m venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest testler -q   # 73 test, GPU gerekmez
```

## vLLM sunucusu (1× H100 80 GB)

```bash
vllm serve Qwen/Qwen3.8-27B \
  --served-model-name Qwen3.8-27B \
  --reasoning-parser qwen3 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.92 \
  --max-num-seqs 64 \
  --enable-prefix-caching \
  --port 8000
```

- Bu komut **doğrulanmadı** (geliştirme makinesinde GPU yok). Önce `00a_vllm_dogrula.py`'yi çalıştırın.
- `--reasoning-parser qwen3` izi `reasoning_content` alanına ayırır. Yeni vLLM sürümleri alanı
  `reasoning` olarak da verir; istemci ikisini de okur, parser yoksa içerikteki `<think>` etiketini ayırır.
- Model hibrit mimarili: kullandığınız vLLM sürümü önek önbelleğini (prefix caching) bu mimaride
  desteklemiyorsa `--enable-prefix-caching`'i kaldırın.
- Model görsel girdi de alıyor. Bellek kazanmak için sürümünüz destekliyorsa
  `--limit-mm-per-prompt '{"image": 0}'` ekleyebilirsiniz.
- 27B bf16 ağırlıklar yaklaşık 54 GB tutar; geri kalan KV önbelleğine gider. `eszamanli: 32`
  (config) ile `--max-num-seqs` uyumlu olmalı.
- Örnekleme değerleri (`config.yaml` → `ogretmen_ornekleme`, `ogrenci_ornekleme`) başlangıç
  tahminidir. Model kartında önerilen değerler (ör. `top_k: 20`, `min_p: 0`, `presence_penalty`)
  varsa buraya yazın; standart dışı anahtarlar vLLM'e `extra_body` ile gider.

## Çalıştırma sırası

| # | Betik | GPU | Girdi → Çıktı |
|---|---|---|---|
| 0a | `betikler/00a_vllm_dogrula.py` | ✔ | sunucu → ekran (çıkış kodu 1 ise **durun**) |
| 0b | `betikler/00b_veri_eslesme_dogrula.py` | – | HF → ekran (EN/TR eşleme, 20 rastgele satır) |
| 1 | `betikler/01_sorulari_hazirla.py` | – | HF → `veri/sorular_train.jsonl`, `veri/sorular_test.jsonl`, `veri/elenen_sorular.jsonl` |
| 2a | `betikler/02a_senaryo_olustur.py` | – | sorular_train → `veri/senaryolar.jsonl` |
| 2b | `betikler/02b_acilis_uret.py` | ✔ | senaryolar → `veri/senaryolar_acilisli.jsonl`, `veri/atilan_senaryolar.jsonl` |
| 3 | `betikler/03_simulasyon.py` | ✔ | senaryolar_acilisli → `veri/ham_diyaloglar.jsonl`, `veri/atilan_diyaloglar.jsonl`, `loglar/denemeler.jsonl` |
| 4 | `betikler/04_pilot_rapor.py` | – | → ekran + `loglar/pilot_rapor.md` |
| 5 | `betikler/05_egitim_formatina_cevir.py` | – | ham_diyaloglar + denemeler → `veri/sft.jsonl`, `veri/dpo_adaylari.jsonl` |

```bash
PY=.venv/bin/python
$PY betikler/00a_vllm_dogrula.py
$PY betikler/01_sorulari_hazirla.py
$PY betikler/02a_senaryo_olustur.py
$PY betikler/02b_acilis_uret.py --limit 200          # pilot
$PY betikler/03_simulasyon.py --tek gsm8k_train_1__s0 --ayrintili   # tek diyalog, her deneme ekranda
$PY betikler/03_simulasyon.py --limit 200
$PY betikler/04_pilot_rapor.py
$PY betikler/05_egitim_formatina_cevir.py            # --tam-diyalog, --tur-siniri-dahil
```

GPU olmadan bütün boru hattı `--sahte` bayrağıyla (02b, 03) uçtan uca çalışır. Sahte istemci kural
tabanlıdır ve hakemin ret yollarını sınamak için ilk denemelerde belirli olasılıkla bilerek kural
ihlali üretir (`config.yaml` → `sahte`). Sahte çıktıyı gerçek `veri/` klasörüne karıştırmamak için
`dizinler`'i başka yere yönlendiren ayrı bir config kullanın (testler bunu `tmp_path` ile yapar).

Bütün çıktılar JSONL'dir ve ekleme modunda yazılır. Her betik kaldığı yerden devam eder: çıktıda zaten
bulunan `id`'leri atlar. Ağ hatasıyla yarım kalan diyalog/açılış hiçbir dosyaya yazılmaz, sonraki
çalıştırmada yeniden denenir. Rastgelelik `seed` + kayıt kimliğinden türetildiği için yeniden
çalıştırmalar aynı senaryoları üretir.

## Klasör yapısı

```
config.yaml                 model adı, eşikler, oranlar, örnekleme (koda gömülü değer yok)
istemler/                   TASLAK istemler (HTML yorumları modele gönderilmez)
  ogretmen_sistem_v1.md     yalnızca davranış; cevap/senaryo/dil talimatı yok
  ogrenci_tur_v1.md         her turda güncel durumla doldurulan öğrenci şablonu
  ogrenci_acilis_v1.md      açılış tipine göre bölümlü şablon
  ogrenci_tanimlar_v1.yaml  hata tipi / persona / taktik / üslup açıklamaları (yalnızca öğrenciye)
  yasakli_ifadeler.yaml     hakemin ifade listeleri
src/
  sayilar.py                EN/TR sayı ayrıştırma, toleranslı karşılaştırma
  gsm8k.py                  socratic ayrıştırma, EN/TR kayma tespiti
  senaryo.py                senaryo üretimi, uyumluluk kuralları, IPF ortak dağılımı
  durum.py                  OgrenciDurumu
  hakem.py                  deterministik hakem (LLM çağırmaz)
  istemler.py               şablon doldurma, JSON şemaları
  llm_istemci.py            vLLM istemcisi (JSON zorlama sarmalayıcısı) + sahte istemci
  diyalog.py                diyalog döngüsü, rol çevirme
  ortak.py                  config, JSONL, hash, tohumlama
betikler/  testler/  veri/  loglar/
```

## Bölüm 3 doğrulama sonuçları

1. **vLLM, düşünme açık/kapalı, `reasoning_content`:** geliştirme makinesinde GPU yok, bu yüzden
   **doğrulanmadı**. `00a_vllm_dogrula.py` sunucuda bunu yapar (taklit bir sunucuya karşı sınandı).
   Zorunlu kontrollerden biri başarısız olursa çıkış kodu 1'dir: talimat gereği durun ve raporlayın.
2. **JSON şeması parametresi:** sürüme göre değişiyor. Sarmalayıcı `response_format` (json_schema),
   `structured_outputs` (vLLM ≥0.10) ve eski `guided_json`'ın üçünü de destekliyor. `json_zorlama: auto`
   sırayla dener ve çalışanı hatırlar; `00a` hangisinin çalıştığını söyler.
3. **EN/TR satır eşleşmesi: birebir DEĞİL.** `malhajar/gsm8k-tr` (config adı `socratic`, doğrulandı)
   EN'nin ilk satırını içermiyor: train 7472 / test 1318 satır (EN: 7473 / 1319). Doğru eşleme
   **TR[i] = EN[i+1]**. Bu kaymayla son cevaplar train'de 7472/7472, test'te 1318/1318 tutuyor;
   20 rastgele satırın kontrolü `loglar/veri_eslesme_dogrulama.txt` dosyasında. `01` kaymayı her bölüm
   için otomatik bulur (uyum %95'in altındaysa durur) ve her satırı ayrıca son cevapla doğrular.
   EN satır 0'ın (Natalia) Türkçe karşılığı yok, `tr_karsiligi_yok` nedeniyle elenir.
4. **Virgüllü ondalık:** doğrulandı (ör. `<<12/60=0,2>>0,2`; TR train'de 363 satır). Değerler her
   zaman İngilizce sürümden alınır; TR'den yalnızca soru metni ve alt sorular kullanılır.

### `01` sonuçları (train)

Toplam 7473 soru: 7260 kabul, 213 elendi (212 `sayi_kumesi_farkli`, 1 `tr_karsiligi_yok`). Elenenlerin
çoğu gerçek çeviri sorunu: sayı değişmiş (18 feet → 5 metre), kaybolmuş ("2 more than" → yok), birim
dönüşmüş (sq ft → m2) ya da kelime ↔ rakam dönüşümü olmuş (Thirty → 30).
Uyarılar (elemez): `degersiz_adim` 1543 (çoğu "Therefore, X kept 36 apples." gibi etiketsiz özet
satırları), `son_adim_son_cevaptan_farkli` 594.
Adım sayısı: 2:1915, 3:2088, 4:1607, 5:925, 6:405, 7:219, 8:89, 9:12.

### `02a` sonuçları

21 780 senaryo. Uyumluluk kuralları, bağımsız örnekleyip uyumsuzları atarak değil, uyumlu üçlüler
(şablon, açılış, davranış) üzerinde **IPF ile marjinalleri config oranlarına uydurulmuş bir ortak
dağılımla** uygulanıyor. Reddetmeli örneklemede `bir_hatali` %38'e çıkıyordu; IPF ile:
bilgi şablonu 0.28 / 0.28 / 0.27 / 0.17, açılış 0.25 / 0.25 / 0.21 / 0.28, davranış ≈0.20.
Kalan sapma 2 adımlı sorulardan (%26) geliyor: bu sorularda `hatali_ve_kilitli` mümkün değil.

## Bilinen sınırlar

- **Yazıyla sayılar** ("on iki", "yarım", "twelve", "half") ayrıştırılmaz. Sızıntı kontrolü bunları
  kaçırır; sayı kümesi karşılaştırmasında da kelime ↔ rakam çevirisi elemeye yol açar.
- Dil tespiti basit bir sezgisel yöntem (Türkçe karakter + sık kelime oranı). 2'den az işaretli
  kelimesi olan kısa mesajlar "belirsiz" sayılır ve geçer.
- `hatali_erken_dogru` kelime-kökü (ilk 5 harf) örtüşmesine dayanan sezgisel bir kontrol. Emin
  olunamayan durumlar yalnızca uyarı olarak loglanır.
- Kilidin açılması (`kilit_acildi`) öğrencinin beyanıdır; Python ipucunun yeterliliğini doğrulayamaz,
  yalnızca loglar (`olaylar`).
- Sızıntı kontrolü sıkı tarafta: kesirlerin parçaları ve belirsiz biçimlerin bütün yorumları
  (`1.250` → 1250 ve 1,25) yasak değerlerle karşılaştırılır. Küçük adım değerleri (ör. 2) yanlış
  pozitif üretebilir; `04` raporundaki `sizinti` oranını izleyin.
- Değeri bilinmeyen (etiketsiz) adımlar doğrulanamaz: öğrenci denediğini bildirince tamamlanmış sayılır.
- Öğretmen cevabındaki markdown/LaTeX ret nedeni değil, yalnızca uyarı (talimatın öğretmen kod listesinde yok).
- Sahte istemci gerçek model davranışını temsil etmez; yalnızca boru hattını ve hakem yollarını sınar.

## VARSAYIM listesi

Kodda `# VARSAYIM:` olarak işaretli olanlar:

| Yer | Varsayım |
|---|---|
| `01` | EN/TR son cevapları uyuşmayan satır `en_tr_son_cevap_farkli` olarak elenir (ek kural). |
| `01` | "Son adım değeri ≠ son cevap" elemez, yalnızca `uyarilar`'a yazılır. |
| `src/gsm8k.py` | `**` içermeyen satırın alt sorusu boş, tamamı açıklama sayılır. |
| `src/senaryo.py` | `hatali`/`kilitli` yalnızca değeri bilinen adımlara atanır. |
| `src/senaryo.py` | `yanlis_denemeli` + `hatali_ve_kilitli`'de hatalı adım kilitli adımdan önce gelir. |
| `src/senaryo.py` | "Listeden sırayla seçilmiş" taktikler: rastgele n taktik, listedeki sırasıyla dizilir. |
| `src/istemler.py` | `on_ek + soru + son_ek` birleştirilirken ek boş değilse araya tek boşluk konur. |
| `src/hakem.py` | Açılışta kelime sınırı, dil ve biçim kopyala/cevabı_ne için yalnızca eklere uygulanır. |
| `src/hakem.py` | Tek başına `$5` LaTeX sayılmaz; `$…$`, `$$`, `\(`, `\frac` vb. sayılır. |
| `src/hakem.py` | `hatali_erken_dogru`: hata hiç yapılmadı ve hiçbir öğretmen mesajı adımla ilgili değil → ret; hata yapılmış ama son öğretmen mesajı ilgisiz görünüyor → uyarı. |
| `src/hakem.py` | Kilit aynı mesajda açılıp doğru değer verilebilir. |
| `src/hakem.py` | "2. adım" gibi sıra sayıları sızıntı/erken sonuç sayılmaz. |
| `src/hakem.py` | Öğretmen cevabındaki markdown/LaTeX yalnızca uyarıdır. |
| `src/durum.py` | `yanlis_denemeli`/`kontrol_isteyen` açılışında baştan itibaren doğru değeri geçen `biliyor` adımlar tamamlanır; hatalı adımdaki yanlış değer bir yanlış deneme sayılır; `kontrol_isteyen` + `hepsi_biliyor` + doğru son cevap → tüm adımlar tamam. |
| `src/durum.py` | Çoklu tahmin (`tahmin_listesi` ≥ 2) bir adımı tamamlamaz. |
| `src/durum.py` | Değeri bilinmeyen adım, öğrenci onu denediğini bildirince tamamlanır. |
| `src/durum.py` | Son cevaba eşit değer verildiyse ardından gelen değersiz/özet adımlar da tamamlanır. Son adımda son cevap da doğru kabul edilir. |
| `src/durum.py` | Kilit, denenen adım kilitliyse onda, değilse aktif adımda açılır. |
| `src/diyalog.py` | Son cevap ya da kapatma son turda gelirse öğretmenin kapanış turu `maks_ogretmen_turu` dışında sayılır. |
| `src/diyalog.py` | Tur sınırında son öğretmen mesajına öğrenci cevabı üretilmez. |
| `03` | `--tek` hata ayıklama modudur; `--kaydet` verilmedikçe dosyalara yazmaz. |
| `05` | Kategori eşlemesinde birden çok kural uyarsa talimattaki sıra önceliklidir. |
| `05` | `dogru_cevap` Türkçe biçimde yazılır (ondalık virgül). |
| `05` | DPO adayları SFT ile aynı bitiş filtresinden geçer. |

Talimatta olmayan ek tasarım kararları:

- Öğrenci "tekrar" eşiği ayrı: `ogrenci_tekrar_esik: 0.9` ("birebir/çok benzer").
- Açılış kontrolüne ek kodlar: `soru_metni_yok`, `ekte_sayi`, `talep_yok`, `deger_yok`, `deger_dogru`,
  `deger_tutarsiz`, `son_cevap_var`, `erken_sonuc`, `kontrol_deger_hatali`.
- `--tek` dışında atılan diyaloglar `veri/atilan_diyaloglar.jsonl`'a yazılır (kaldığı yerden devamda atlanır).
- Persona/hata tipi açıklama metinleri koddan ayrı, `istemler/ogrenci_tanimlar_v1.yaml`'da; hash'i
  `istem_surumleri`'ne girer.
- `sft.jsonl` anahtar sırası talimattaki örnekle aynı; asistan mesajında `content` önce, `reasoning_content` sonra.
