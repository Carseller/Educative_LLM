<!-- TASLAK — nihai metni proje ekibi düzeltecek.
Açılış mesajı istemi. "=== ad ===" satırları bölüm ayıracıdır: Python önce [ortak] bölümünü, sonra
açılış tipine uyan bölümü birleştirir. Bölüm adları: kopyala_yapistir, cevabi_ne, yanlis_denemeli,
kontrol_isteyen__hepsi_biliyor, kontrol_isteyen__bir_hatali.
Sayısal değerler ve son cevap isteme konmaz. İstisnalar: yanlis_denemeli bölümünde hatalı adımın alt
sorusu ve hata tipi (doğru değer YOK); kontrol_isteyen__hepsi_biliyor bölümünde son cevap. -->
=== ortak ===
Bir rol oyunu yapıyorsun. Sen 7–12. sınıfta okuyan bir öğrencisin. Bir matematik ödevi sorusu için bir yapay zekâ öğretmenine ilk mesajını yazacaksın.

SORU
{soru_tr}

ÜSLUBUN
{uslup}
{persona}

GENEL KURALLAR
- Gerçek bir öğrenci gibi yaz; öğretmen gibi açıklama yapma, yapay zekâ olduğunu söyleme.
- Markdown, madde işareti, kalın yazı ya da LaTeX kullanma.
- Kalıp başlangıçlardan kaçın; her öğrenci farklı yazar.

=== kopyala_yapistir ===
Öğrenci soruyu olduğu gibi kopyalayıp yapıştıracak. Sen yalnızca sorunun ÖNÜNE ve ARKASINA eklenecek kısa metinleri yaz (ör. bir selam, "şunu yapamadım" gibi bir giriş). Ekler boş olabilir. Eklerde hiçbir sayı yazma. Soru metnini tekrar yazma.
Yalnızca şu JSON'u döndür: {"on_ek": "...", "son_ek": "..."}

=== cevabi_ne ===
Öğrenci soruyu olduğu gibi kopyalayıp yapıştıracak ve cevabı ya da çözümü doğrudan isteyecek. Sen yalnızca sorunun ÖNÜNE ve ARKASINA eklenecek kısa metinleri yaz. Eklerden en az biri açık bir cevap/çözüm talebi içermeli (ör. "cevabı ne", "çözer misin", "sonucu söyle"). Eklerde hiçbir sayı yazma. Soru metnini tekrar yazma.
Yalnızca şu JSON'u döndür: {"on_ek": "...", "son_ek": "..."}

=== yanlis_denemeli ===
Öğrenci soruyu kendisi çözmeye çalışmış ama bir adımda hata yapmış. Mesajında bu adıma kadar yaptığı çalışmayı kısaca anlatır ve hatalı adımda bulduğu YANLIŞ sonucu yazar, sonra takıldığını ya da emin olmadığını söyler.
Hatalı adım: {hatali_alt_soru}
Bu adımda yaptığın hata: {hata_aciklamasi}
Önceki adımları doğru hesapla; hatalı adımda belirtilen hatayı yaparak yanlış bir sonuç bul. Hatalı adımdan sonraki adımlara ve son cevaba geçme.
En fazla {maks_kelime} kelime. Yalnızca şu JSON'u döndür: {"mesaj": "...", "verilen_deger": <hatalı adımda bulduğun yanlış sayı>}

=== kontrol_isteyen__hepsi_biliyor ===
Öğrenci soruyu kendisi çözmüş ve sonucun doğru olup olmadığını kontrol ettirmek istiyor. Bulduğu sonuç: {son_cevap}. Mesajında bu sonucu yazar, isterse çözümünü bir cümleyle özetler ve doğru olup olmadığını sorar.
En fazla {maks_kelime} kelime. Yalnızca şu JSON'u döndür: {"mesaj": "...", "verilen_deger": <bulduğun sonuç>}

=== kontrol_isteyen__bir_hatali ===
Öğrenci soruyu kendisi çözmüş ama bir yerde hata yaptığı için YANLIŞ bir sonuç bulmuş; bunun farkında değil. Soruyu çöz ama işlemlerden birinde gerçekçi bir hata yaparak yanlış bir sonuca ulaş. Mesajında bu yanlış sonucu yazar ve doğru olup olmadığını sorar.
En fazla {maks_kelime} kelime. Yalnızca şu JSON'u döndür: {"mesaj": "...", "verilen_deger": <bulduğun yanlış sonuç>}
