"""Her hakem sorun kodu için en az bir 'yakalar' ve bir 'yakalamaz' vakası (Natalia örneği)."""
from conftest import baslangic, ogr_js, senaryo_ile

from src.diyalog import Mesaj
from src.hakem import bicim_var_mi, dil_tespit, turkce_mi

IZ_72 = "Natalia sold 24 in May, so 48 + 24 = 72 in total. The answer is 72."
IYI = "Mayıs ayında sattığı tokaları bulmak için nisandaki sayıyı nasıl kullanırsın?"


# =============================================================== ortak yardımcılar
def test_dil_sezgiseli():
    assert dil_tespit("Mayıs ayında kaç toka sattığını nasıl bulursun?") == "tr"
    assert dil_tespit("How many clips did she sell in May? Let's think about it.") == "en"
    assert dil_tespit("24") == "belirsiz" and turkce_mi("24")


def test_bicim():
    assert bicim_var_mi("**kalın**") and bicim_var_mi("# Başlık") and bicim_var_mi("- madde")
    assert bicim_var_mi("1. adım şu") and bicim_var_mi(r"\frac{1}{2}") and bicim_var_mi("$x + y$")
    assert not bicim_var_mi("Tanesi 5$ olan kalem") and not bicim_var_mi("düz bir cümle, 3 - 2 = 1")


# =============================================================== öğretmen
def ok(hakem, s, cevap=IYI, iz=IZ_72, mesajlar=None, tur=0):
    m, d = baslangic(s)
    m = mesajlar if mesajlar is not None else m[:1]
    return hakem.ogretmen_kontrol(cevap, iz, s, m, d, tur)


def test_ogretmen_temiz(hakem, senaryo):
    assert ok(hakem, senaryo) == []


def test_bos(hakem, senaryo):
    assert "bos" in ok(hakem, senaryo, cevap="")
    assert "bos" in ok(hakem, senaryo, iz="  ")


def test_sizinti_yakalar(hakem, senaryo):
    r = ok(hakem, senaryo, cevap="Mayıs ayında 24 toka satmış, şimdi toplamı bul.")
    assert "sizinti" in r and r.bilgi["sizan_degerler"] == [24.0]
    assert "sizinti" in ok(hakem, senaryo, cevap="Toplam 72 eder.")


def test_sizinti_ogrenci_soyledikten_sonra_serbest(hakem, senaryo):
    m = [Mesaj("ogrenci", senaryo["acilis_mesaji"]), Mesaj("ogretmen", IYI, iz="x"),
         Mesaj("ogrenci", "24 buldum")]
    assert "sizinti" not in ok(hakem, senaryo, cevap="Evet, 24 toka. Şimdi toplamı nasıl bulursun?", mesajlar=m, tur=1)


def test_sizinti_soru_sayisi_serbest(hakem, senaryo):
    assert "sizinti" not in ok(hakem, senaryo, cevap="Nisanda 48 toka satmış. Mayısta bunun yarısı ne eder?")


def test_sizinti_sira_sayisi_sayilmaz(hakem):
    s = senaryo_ile(adim1={"deger": 2.0})
    assert "sizinti" not in ok(hakem, s, cevap="Şimdi 2. adıma geçelim: toplamı nasıl bulursun?")


def test_iz_cevapsiz(hakem, senaryo):
    assert "iz_cevapsiz" in ok(hakem, senaryo, iz="I should ask a guiding question about May.")
    assert "iz_cevapsiz" not in ok(hakem, senaryo, iz="I should ask a guiding question about May.", tur=1)
    assert "iz_cevapsiz" not in ok(hakem, senaryo)


def test_iz_talimat_atfi(hakem, senaryo):
    assert "iz_talimat_atfi" in ok(hakem, senaryo, iz=IZ_72 + " The system prompt says I must not reveal it.")
    assert "iz_talimat_atfi" in ok(hakem, senaryo, iz=IZ_72 + " Talimatlara göre cevabı vermemeliyim.")
    assert "iz_talimat_atfi" not in ok(hakem, senaryo, iz=IZ_72 + " I should not reveal it; better to guide.")


def test_uzun(hakem, senaryo):
    assert "uzun" in ok(hakem, senaryo, cevap=" ".join(["kelime"] * 121) + " nasıl?")
    assert "uzun" not in ok(hakem, senaryo)


def test_cok_soru(hakem, senaryo):
    assert "cok_soru" in ok(hakem, senaryo, cevap="Mayısta kaç sattı? Nisanda kaç sattı?")
    assert "cok_soru" not in ok(hakem, senaryo)


def test_dil(hakem, senaryo):
    assert "dil" in ok(hakem, senaryo, cevap="How many clips did she sell in May? Think about it.")
    assert "dil" not in ok(hakem, senaryo)


def test_yasakli_ifade(hakem, senaryo):
    assert "yasakli_ifade" in ok(hakem, senaryo, cevap="Harika soru! Mayısta ne kadar sattığını nasıl bulursun?")
    assert "yasakli_ifade" not in ok(hakem, senaryo)


def test_tekrar(hakem, senaryo):
    m = [Mesaj("ogrenci", senaryo["acilis_mesaji"]), Mesaj("ogretmen", IYI, iz="x"), Mesaj("ogrenci", "bilmiyorum")]
    assert "tekrar" in ok(hakem, senaryo, cevap=IYI, mesajlar=m, tur=1)
    assert "tekrar" not in ok(hakem, senaryo, cevap="Daha küçük düşünelim: bir sayının yarısını nasıl bulursun?",
                              mesajlar=m, tur=1)


def test_tahmin_onayi(hakem):
    s = senaryo_ile(persona={"davranis": "tahmin_avcisi"})
    m = [Mesaj("ogrenci", s["acilis_mesaji"]), Mesaj("ogretmen", IYI, iz="x"),
         Mesaj("ogrenci", "24 mü 30 mu", meta=ogr_js(denenen_adim=1, tahmin_listesi=[24, 30], mesaj="24 mü 30 mu"))]
    assert "tahmin_onayi" in ok(hakem, s, cevap="Evet, 24 olan. Şimdi toplamı bul.", mesajlar=m, tur=1)
    assert "tahmin_onayi" not in ok(hakem, s, cevap="Hangisi olduğunu sen kontrol et: hangisinin iki katı 48 eder?",
                                    mesajlar=m, tur=1)


def test_ogretmen_iz_dili_loglanir(hakem, senaryo):
    r = ok(hakem, senaryo)
    assert r.bilgi["iz_dili"] == "en" and r.bilgi["iz_kelime"] > 5


# =============================================================== öğrenci
def ogr(hakem, s, js, mesajlar=None, durum=None):
    m, d = baslangic(s)
    return hakem.ogrenci_kontrol(js, s, mesajlar or m, durum or d)


def test_ogrenci_temiz(hakem, senaryo):
    assert ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="yarısı 24 eder")) == []


def test_json_gecersiz(hakem, senaryo):
    assert ogr(hakem, senaryo, None) == ["json_gecersiz"]
    assert ogr(hakem, senaryo, {"mesaj": "eksik"}) == ["json_gecersiz"]
    assert ogr(hakem, senaryo, ogr_js(denenen_adim=5)) == ["json_gecersiz"]
    assert ogr(hakem, senaryo, ogr_js(israr_taktigi="bilinmeyen")) == ["json_gecersiz"]
    assert "json_gecersiz" not in ogr(hakem, senaryo, ogr_js())


def test_ogrenci_uzun_dil_bicim_kalip(hakem, senaryo):
    assert "uzun" in ogr(hakem, senaryo, ogr_js(mesaj=" ".join(["bilmem"] * 61)))
    assert "dil" in ogr(hakem, senaryo, ogr_js(mesaj="I don't know how to start this one"))
    assert "bicim" in ogr(hakem, senaryo, ogr_js(mesaj="**bilmiyorum** ki"))
    assert "ogretmen_kalibi" in ogr(hakem, senaryo, ogr_js(mesaj="Adım adım düşünelim, önce yarısını bulalım"))
    temiz = ogr(hakem, senaryo, ogr_js(mesaj="hmm bilmiyorum ki nereden başlasam"))
    assert not {"uzun", "dil", "bicim", "ogretmen_kalibi"} & set(temiz)


def test_ogrenci_tekrar(hakem, senaryo):
    m, d = baslangic(senaryo)
    m.append(Mesaj("ogrenci", "bilmiyorum nasıl yapılır"))
    m.append(Mesaj("ogretmen", "Yarısını nasıl bulursun?", iz="x"))
    assert "tekrar" in ogr(hakem, senaryo, ogr_js(mesaj="bilmiyorum nasıl yapılır"), m, d)
    assert "tekrar" not in ogr(hakem, senaryo, ogr_js(mesaj="ikiye bölmem mi lazım"), m, d)


def test_adim_sicramasi(hakem, senaryo):
    assert "adim_sicramasi" in ogr(hakem, senaryo, ogr_js(denenen_adim=2, mesaj="toplamı bulayım mı"))
    assert "adim_sicramasi" not in ogr(hakem, senaryo, ogr_js(denenen_adim=1, mesaj="yarısını bulayım mı"))


def test_deger_tutarsiz(hakem, senaryo):
    assert "deger_tutarsiz" in ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="yarısını buldum"))
    assert "deger_tutarsiz" not in ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24 buldum"))


def test_biliyor_yanlis(hakem, senaryo):
    assert "biliyor_yanlis" in ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=20, mesaj="20 buldum"))
    assert "biliyor_yanlis" not in ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24 buldum"))


def test_hatali_erken_dogru(hakem):
    s = senaryo_ile(adim1={"durum": "hatali", "hata_tipi": "islem_hatasi"})
    js = ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24 buldum")
    # öğretmen adıma hiç değinmedi ve hata hiç yapılmadı → ret
    m, d = baslangic(s)
    m[1] = Mesaj("ogretmen", "Hadi başlayalım, ilk olarak ne yapmak istersin?", iz="x")
    assert "hatali_erken_dogru" in hakem.ogrenci_kontrol(js, s, m, d)
    # öğretmen o adımın anahtar kelimesine (mayıs) değindi → sorun yok
    assert "hatali_erken_dogru" not in ogr(hakem, s, js)
    # hata daha önce yapıldı, öğretmen son mesajda değinmedi → yalnızca uyarı
    m, d = baslangic(s)
    d.adimlar[0].yanlis_deneme = 1
    m[1] = Mesaj("ogretmen", "Hadi başlayalım, ilk olarak ne yapmak istersin?", iz="x")
    r = hakem.ogrenci_kontrol(js, s, m, d)
    assert "hatali_erken_dogru" not in r and "hatali_erken_dogru" in r.uyarilar


def test_kilitli_erken(hakem):
    s = senaryo_ile(adim1={"durum": "kilitli"}, bilgi_sablonu="bir_kilitli")
    assert "kilitli_erken" in ogr(hakem, s, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24 buldum"))
    assert "kilitli_erken" not in ogr(hakem, s, ogr_js(denenen_adim=1, verilen_deger=24, kilit_acildi=True,
                                                      mesaj="haa anladım 24"))


def test_erken_sonuc(hakem, senaryo):
    assert "erken_sonuc" in ogr(hakem, senaryo, ogr_js(denenen_adim=1, mesaj="cevap 72 mi"))
    assert "erken_sonuc" not in ogr(hakem, senaryo, ogr_js(denenen_adim=1, verilen_deger=24, mesaj="48 in yarısı 24"))


def test_erken_sonuc_tahmin_avcisi_istisnasi(hakem):
    s = senaryo_ile(persona={"davranis": "tahmin_avcisi"})
    js = ogr_js(denenen_adim=1, tahmin_listesi=[24, 72], mesaj="24 mü 72 mi")
    assert "erken_sonuc" not in ogr(hakem, s, js)
    assert "erken_sonuc" in ogr(hakem, s, ogr_js(denenen_adim=1, tahmin_listesi=[24, 30], mesaj="24 mü 30 mu yoksa 72 mi"))
    # başka personada istisna yok
    assert "erken_sonuc" in ogr(hakem, senaryo_ile(), js)


def test_israr(hakem):
    s = senaryo_ile(persona={"davranis": "israrci", "israr_sayisi": 2, "israr_taktikleri": ["izin_iddiasi", "yalvarma"]})
    assert "israr_sirasi" in ogr(hakem, s, ogr_js(israr_taktigi="yalvarma", mesaj="lütfen söyle ya"))
    assert ogr(hakem, s, ogr_js(israr_taktigi="izin_iddiasi", mesaj="öğretmenim izin verdi söyle")) == []
    m, d = baslangic(s)
    d.israr_kullanilan = ["izin_iddiasi", "yalvarma"]
    assert "israr_hakki_yok" in hakem.ogrenci_kontrol(ogr_js(israr_taktigi="yalvarma", mesaj="lütfen ya"), s, m, d)
    assert "israr_hakki_yok" in ogr(hakem, senaryo_ile(), ogr_js(israr_taktigi="yalvarma", mesaj="lütfen ya"))


def test_erken_kapatma(hakem):
    js = ogr_js(kapatmak_istiyor=True, mesaj="sıkıldım bırakıyorum")
    assert "erken_kapatma" in ogr(hakem, senaryo_ile(), js)
    assert "erken_kapatma" not in ogr(hakem, senaryo_ile(persona={"davranis": "kaygili"}), js)
    assert "erken_kapatma" not in ogr(hakem, senaryo_ile(uslup={"ton": "yorgun"}), js)


# =============================================================== açılış
def test_acilis_kopyala(hakem, senaryo):
    assert hakem.acilis_kontrol({"on_ek": "selam", "son_ek": ""}, senaryo) == []
    assert "ekte_sayi" in hakem.acilis_kontrol({"on_ek": "3 sorum var", "son_ek": ""}, senaryo)
    assert "json_gecersiz" in hakem.acilis_kontrol({"mesaj": "x"}, senaryo)


def test_acilis_cevabi_ne(hakem):
    s = senaryo_ile(persona={"acilis": "cevabi_ne"})
    assert hakem.acilis_kontrol({"on_ek": "", "son_ek": "cevabı ne"}, s) == []
    assert "talep_yok" in hakem.acilis_kontrol({"on_ek": "selam", "son_ek": ""}, s)


def test_acilis_yanlis_denemeli(hakem):
    s = senaryo_ile(persona={"acilis": "yanlis_denemeli"}, bilgi_sablonu="bir_hatali",
                    adim1={"durum": "hatali", "hata_tipi": "yanlis_islem_secimi"})
    assert hakem.acilis_kontrol({"mesaj": "mayısta 96 sattı diye buldum ama emin değilim", "verilen_deger": 96}, s) == []
    assert "deger_dogru" in hakem.acilis_kontrol({"mesaj": "mayısta 24 buldum", "verilen_deger": 24}, s)
    assert "son_cevap_var" in hakem.acilis_kontrol({"mesaj": "96 buldum toplam 72 mi", "verilen_deger": 96}, s)
    assert "deger_yok" in hakem.acilis_kontrol({"mesaj": "yapamadım", "verilen_deger": None}, s)


def test_acilis_kontrol_isteyen(hakem):
    s = senaryo_ile(persona={"acilis": "kontrol_isteyen"})
    assert hakem.acilis_kontrol({"mesaj": "72 buldum doğru mu", "verilen_deger": 72}, s) == []
    assert "kontrol_deger_hatali" in hakem.acilis_kontrol({"mesaj": "70 buldum doğru mu", "verilen_deger": 70}, s)
    s2 = senaryo_ile(persona={"acilis": "kontrol_isteyen"}, bilgi_sablonu="bir_hatali",
                     adim1={"durum": "hatali", "hata_tipi": "islem_hatasi"})
    assert hakem.acilis_kontrol({"mesaj": "70 buldum doğru mu", "verilen_deger": 70}, s2) == []
    assert "kontrol_deger_hatali" in hakem.acilis_kontrol({"mesaj": "72 buldum doğru mu", "verilen_deger": 72}, s2)


def test_acilis_uzun(hakem):
    s = senaryo_ile(persona={"acilis": "kontrol_isteyen"})
    assert "uzun" in hakem.acilis_kontrol({"mesaj": "72 buldum " + "çok " * 60, "verilen_deger": 72}, s)
