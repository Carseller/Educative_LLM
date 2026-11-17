# Eğitici LLM Projesi – Karar Raporu

Oct 3, 2026 · @carseller

## Amaç ve kapsam

Proje, öğrenciye hazır cevap vermek yerine onu sonuca yönlendiren, eğitim amaçlı tek bir dil modeli geliştirecek. Model TÜBİTAK projesi olarak sunulacak; kabul alırsa açık ağırlıklı yayınlanabilir.

- [ ] **Genel + eğitim modu ayrımı yapılmayacak.** Genel mod, "bu ödev değil, iş için lazım" bahanesiyle atlatma yolu açar ve veri ihtiyacını katlar.
- [ ] **Kapsam ayrımı konuya göre değil, işleve göre yapılacak.** Temel kural: cevap, öğrencinin yapması gereken düşünme işini onun yerine yapıyorsa model yönlendirir; ders kitabında hazır duran bilgiyi (tanım, formül) veriyorsa doğrudan cevaplar.
- [ ] **Koruma seviyesi:** Aşırı sıkı bir koruma hedeflenmiyor. Hedef, ortalama bir öğrenci yorulduğunda veya ısrar ettiğinde cevabı doğrudan vermeyen, ama onu sıkıp kaçırmayan bir model.

**Gerçekçi beklenti:** Eğitime gömülü davranış sistem promptundan çok daha dayanıklıdır, ama aşılamaz değildir. Açık ağırlıklı yayında herkes yeniden ince ayar yaparak davranışı geri alabilir.

## Model seçimi

Temel model **Qwen3.8-27B** olacak: 27B parametreli, yoğun (dense), metin ve görsel girdi alan, düşünme modu olan, Apache-2.0 lisanslı bir model ([Hugging Face](https://huggingface.co/Qwen/Qwen3.8-27B)).

- **Dense olması** ince ayarı MoE modellere göre kolaylaştırır.
- **Mimari standart değil:** Qwen3.5'in hibrit Gated DeltaNet + gated attention yapısını kullanıyor. Unsloth bu mimariyi destekliyor ([Unsloth rehberi](https://unsloth.ai/docs/models/qwen3.8/train)); diğer araçlar için uyumluluk ayrıca doğrulanmalı.
- **Düşünme modu:** Varsayılan olarak açık. Eğitim verisinde düşünme izi olmazsa bu davranış bozulabilir; bu yüzden SFT örneklerine düşünme izi eklenecek.
- **Görsel yol:** Model görsel okuyabilir ama üretemez. Görsel girdi eğitilmezse eski davranışa dönen bir arka kapı olur.

## Eğitim yöntemi

Eğitim QLoRA ile iki aşamada yapılacak: önce SFT, sonra DPO. Bellek çok kısıtlı çıkarsa iki aşama yerine tek aşamalı ORPO denenecek.

| Bileşen | Karar | Gerekçe |
| --- | --- | --- |
| Eğitim biçimi | QLoRA (4-bit ana model + LoRA adaptörü) | Bütçe düşük; 27B tek GPU'ya sığar, genel yetenek kaybı azalır |
| Aşama 1: SFT | Çok turlu, düşünme izli, metin + görsel diyaloglar | Öğretmen kişiliği, üslup ve kademeli yardım kalıbını öğretir |
| Aşama 2: DPO | İki yönlü tercih çiftleri | Kalibrasyon: hem cevap sızdırmayı hem gereksiz sorgulamayı cezalandırır |
| Unutma önlemi | Genel amaçlı veri karışımı, düşük öğrenme oranı, az epoch | Türkçe ve genel yeteneklerin korunması |
| LoRA hedefleri | Attention + MLP katmanları | Sadece attention davranış değişikliği için yetmeyebilir |

DPO çiftleri iki yönlü kurulacak: (1) seçilen ipucu, reddedilen doğrudan cevap; (2) seçilen öğrenci konuyu kanıtladıktan sonra kısa yardım, reddedilen hâlâ süren Sokratik sorgu. Yalnızca birinci tür kullanılırsa model her şeyi reddeden, kullanıcıyı bezdiren bir modele dönüşür.

## Model davranışı

Model, düşünme işini öğrencinin yerine yapmadan yönlendirecek; hazır bilgiyi ise doğrudan verecek.

- **Formül ve tanım soruları:** Cevap doğrudan verilir, ardından merak uyandıran kısa bir ek gelebilir (örnek: "çemberin çevresi nedir" → 2πr ve nereden geldiğine dair kısa bir sezgi). Ek kısa ve değişken olacak; bazen hiç olmayacak. Sınav öncesi hızlı kontrol gibi bağlamlarda atlanacak. Bu karar düşünme izinde modellenecek.
- **Kademeli destek:** Öğrenci takılınca veya bırakmak isteyince model aynı ipucunu tekrarlamaz, destek seviyesini değiştirir:
  1. Sorunun daha küçük bir parçasını sormak
  2. Daha somut bir ipucu (hangi kavramın kullanılacağı)
  3. Benzer ama farklı bir problemi adım adım çözüp asıl soruya dönmek
  4. Yorgunluğu kabul edip mola veya daha kolay bir giriş noktası önermek
- Öğrencinin kendi sorusunun cevabı bu basamakların hiçbirinde verilmez.
- **Kilit açma:** Kilit iddiayla değil, kanıtla açılır. "Biliyorum, sadece sonucu ver" diyen öğrenciye kısa bir kontrol sorusu sorulur (kavramı kendi cümlesiyle anlatmak veya benzer bir soruyu çözmek). Bu sadece sohbet içinde geçerli; oturumlar arası hafıza bu aşamada yok.
- **Düşünme izi:** Arayüzde gösterilmeyecek. Bu, iz içinde çözüm bulunmasından kaynaklanan sızıntı riskini ortadan kaldırıyor.
- **Görselle anlatım:** Sohbet içinde Markdown ve LaTeX yeterli.

## Görsel eğitim

Model, görselde de metindeki eğitici tavrı gösterecek şekilde metin ve görsel veriyle birlikte eğitilecek. Görsel kodlayıcı dondurulacak, yalnızca dil modeli kısmı eğitilecek; eğitimde maksimum piksel sınırı konacak.

Görsel bir sohbette model iki adım izleyecek: önce ne okuduğunu kısaca doğrular (algı hatalarına karşı), sonra görsel türüne göre davranır.

| Görsel türü | Model davranışı |
| --- | --- |
| Basılı ödev / çalışma kağıdı | Yönlendirme |
| Çok sorulu sayfa | Bir soru seçip başlamak |
| Öğrencinin doğru çözümü | Onay + kısa geri bildirim |
| Öğrencinin yanlış çözümü | Hatayı düzeltmeden hatalı adımı fark ettirmek |
| Yarım çözüm | Bir sonraki adıma yönlendirme |
| Grafik / tablo | Okuma becerisi gerekiyorsa yönlendirme, bilgi sorusuysa doğrudan cevap |
| Ders kitabı sayfası | Anlatım ve anlama kontrolü |
| Okunamayan görsel | Tahmin yok; daha net fotoğraf veya yazılı soru istemek |
| Görselle metin çelişiyor | Çelişkiyi sormak |
| "Kağıdı benim için doldur" | Biçim değişmiş ödev isteği; yönlendirme |

**Veri kaynakları:**

- Ana kaynak: LaTeX/HTML'den render edilen sorular + gerçekçi bozulmalar (eğiklik, gölge, bulanıklık). Doğru metin ve cevap bilindiği için diyalog üretimi algı hatasından etkilenmez.
- Ekip ve gönüllü yetişkinlerin el yazısıyla, bilinçli hatalar içeren çözümleri.
- Lisansı uygun açık veri setleri (MathVista, Geometry3K, ChartQA vb.); MEB/ÖSYM içerikleri için kullanım koşulları kontrol edilecek.
- Gerçek öğrenci ödevleri KVKK, reşit olmayanlar ve etik kurul nedeniyle ana kaynak olmayacak.

Ayrı bir görsel değerlendirme seti kurulacak: okuma doğruluğu, uydurma oranı, cevap sızdırma ve aynı sorunun metin/görsel tutarlılığı.

## Vazgeçilen ve ertelenen fikirler

İlk aşamada mümkün görülen birkaç fikir kapsam dışına çıkarıldı veya sonraya bırakıldı.

| Fikir | Durum | Gerekçe |
| --- | --- | --- |
| Genel + eğitim modlu tek model | Vazgeçildi | Ayrım zor, genel mod atlatma yolu açar, veri ihtiyacını katlar |
| Eğitime gömerek "aşılamaz" model | Beklenti düzeltildi | İnce ayar dayanıklılık sağlar ama aşılmazlık sağlamaz; hedef aşırı sıkı koruma değil |
| Tam parametre ince ayar | Vazgeçildi | 27B için çoklu GPU gerektirir, bütçe dışı |
| RLHF (PPO + ödül modeli) | Vazgeçildi | Pahalı ve kararsız; DPO aynı amaca daha ucuz ulaşır |
| Çok turlu RL (GRPO, simüle öğrenci) | Ertelendi | Ödül fonksiyonu ve hakem model gerektirir; ödül hacklemeye açık |
| Çalışma anında judge LLM | Ertelendi | Şu an kurulmayacak (veri üretiminde güçlü bir modeli API ile kullanmak ayrıca değerlendirilecek) |
| Öğrenci veritabanı / oturumlar arası hafıza | Ertelendi | Ağırlıklar kullanıcıyı hatırlamaz; bu bir sistem mimarisi işi |
| Düşünme izini arayüzde göstermek | Vazgeçildi | İzde çözüm sızıntısı riski |
| Modelin görsel çıktı üretmesi (SVG, grafik kodu) | Vazgeçildi | Model görsel üretemez; Markdown + LaTeX yeterli |
| Gerçek öğrenci ödevleriyle görsel veri | Ana kaynak olmaktan çıkarıldı | KVKK, reşit olmayanlar, etik kurul |
| Ana eğitimi Colab'da yapmak | Ana yol olmaktan çıkarıldı | GPU garantisi yok, oturum kopabilir; geliştirme ve yedek için tutuluyor |
| Gri alanlar (kompozisyon, çeviri, kod yazdırma) | Ertelendi | Sonraki aşamada ayrıntılı işlenecek |
| Kademeli desteğin öğrenci psikolojisine göre ayarı | Ertelendi | Sonraki aşamada derinleştirilecek |

## GPU kaynağı

Hedef 80 GB'lık tek bir A100 veya H100; pratik alt sınır 48 GB. Unsloth'a göre QLoRA 24 GB ile çalışıyor ([Unsloth](https://unsloth.ai/docs/models/qwen3.8/train)), ama uzun çok turlu diziler, düşünme izi, görsel tokenlar ve DPO'nun çift işleme yükü bu sınırı yetersiz kılıyor. Eğitim süresi, birkaç yüz örneklik bir pilotla ölçülecek.

| Yol | Kullanım amacı | Maliyet / koşul | Risk |
| --- | --- | --- | --- |
| [Kaggle](https://unsloth.ai/docs/models/qwen3.8/train) | Kod ve veri formatı hata ayıklama | Ücretsiz, haftada \~30 saat 2× T4 | T4 yavaş, bf16 yok; gerçek eğitim için uygun değil |
| [Google Colab Pro / Pro+](https://aicoolies.com/pricing/google-colab) | Pilot ve yedek eğitim ortamı | Pro 9,99 $/ay (100 birim), Pro+ 49,99 $/ay; A100 birim tüketimi kaynaklara göre değişiyor, panelden doğrulanmalı | GPU garantisi yok, oturum kopabilir, disk geçici |
| Saatlik GPU kiralama ([Lambda](https://www.thundercompute.com/blog/colab-alternatives-for-cheap-deep-learning-in-2025), RunPod, Thunder Compute) | Ana eğitim (TRUBA yoksa) | A100 80 GB yaklaşık 1–2 $/saat; güncel fiyat doğrulanmalı | Bütçe takibi gerekir |
| [TRUBA (TÜBİTAK ULAKBİM)](https://docs.truba.gov.tr/0-truba/uyelik_rehberi.html) | Ana eğitim (tercih edilen) | Akademik kullanım ücretsiz; proje kapsamında öncelikli kullanım ücretli ve bütçeye yazılabilir | Lisans öğrencileri danışmanlı bir proje hesabı üzerinden erişebiliyor |
| [Herkes İçin GPU programı](https://dijipedya.com/herkes-icin-gpu-programi-nedir-basvuru-ne-zaman/) | Ek kaynak | GPU-saat kredisi; TRUBA üzerinden kullanılabilecek | Başvuru takvimi henüz belli değil |

**Uygulama sırası:**

1. Veri formatı ve eğitim kodunu küçük bir modelde (Qwen3.5-4B/9B) Kaggle veya Colab'da geliştirmek.
2. 27B ile A100 80 GB'da birkaç yüz örneklik pilot: bellek ve hız ölçümü, maliyet hesabı.
3. Ana eğitimi TRUBA'da, erişim yoksa saatlik kiralanan GPU'da yapmak.

**Teknik notlar:** Unsloth + TRL (SFT ve DPO eğitmenleri) Colab'da çalışır. T4 yerine A100 seçilmeli. Görsel girdili DPO desteği pilotta test edilmeli. Sadece LoRA adaptörü kaydedilmeli (birleştirilmiş model yaklaşık 55 GB); checkpoint'ler düzenli olarak Drive'a yazılmalı.

## Açık sorular ve sonraki adımlar

Kaynak planlaması ve veri seti tasarımı bu soruların cevabına bağlı.

- [ ] Proje hangi TÜBİTAK programına başvuruyor ve bir akademisyen danışman var mı? (TRUBA erişimi buna bağlı)
- [ ] Veri üretiminde güçlü bir modeli API üzerinden üretici/hakem olarak kullanmak kabul edilecek mi?
- [ ] Değerlendirme seti eğitimden önce kurulacak: cevap sızdırma, gereksiz reddetme, uzun sohbette tutarlılık, genel yetenek kaybı.
- [ ] Veri seti şeması: senaryo türleri, metin/görsel oranı, bir SFT örneği ve bir DPO çiftinin formatı.
- [ ] Gri alanlar (kompozisyon, çeviri, kod) için kurallar.
- [ ] Kademeli desteğin öğrenci psikolojisine göre ayarlanması.
- [ ] Görsel girdili DPO'nun araç desteğinin pilotta test edilmesi.

## Kaynaklar

- [Qwen/Qwen3.8-27B – Hugging Face](https://huggingface.co/Qwen/Qwen3.8-27B)
- [Qwen3.8 Fine-tuning Guide – Unsloth](https://unsloth.ai/docs/models/qwen3.8/train)
- [Google Colab Pricing (2026) – aicoolies](https://aicoolies.com/pricing/google-colab)
- [Colab alternatives – Thunder Compute](https://www.thundercompute.com/blog/colab-alternatives-for-cheap-deep-learning-in-2025)
- [TRUBA Üyelik Rehberi](https://docs.truba.gov.tr/0-truba/uyelik_rehberi.html)
- [Herkes İçin GPU Programı – Dijipedya](https://dijipedya.com/herkes-icin-gpu-programi-nedir-basvuru-ne-zaman/)
