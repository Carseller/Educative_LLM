import asyncio
import copy
from collections import Counter

from conftest import NATALIA_SENARYO, ogr_js, senaryo_ile

from src.diyalog import DiyalogAyar, Mesaj, diyalog_calistir, ogrenciye_gecmis, ogretmene_gecmis
from src.durum import OgrenciDurumu
from src.hakem import Hakem
from src.istemler import Istemler, acilis_birlestir
from src.llm_istemci import SahteIstemci, iz_ayir, json_coz
from src.senaryo import ortak_dagilim, soru_senaryolari, uyumluluk_ihlali


# ================================================================== durum
def test_durum_dogru_deger_tamamlar():
    d = OgrenciDurumu.baslat(senaryo_ile())
    assert d.aktif_adim == 1
    d.guncelle(ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24"))
    assert d.adimlar[0].tamamlandi and d.aktif_adim == 2 and not d.son_cevap_verildi
    d.guncelle(ogr_js(denenen_adim=2, verilen_deger=72, mesaj="72"))
    assert d.son_cevap_verildi and not d.tamamlandi
    d.ogretmen_turu_eklendi()
    assert d.tamamlandi


def test_durum_hata_duzeltildi_ve_yanlis_deneme():
    d = OgrenciDurumu.baslat(senaryo_ile(adim1={"durum": "hatali", "hata_tipi": "islem_hatasi"}))
    d.guncelle(ogr_js(denenen_adim=1, verilen_deger=96, mesaj="96"))
    assert d.adimlar[0].yanlis_deneme == 1 and not d.adimlar[0].tamamlandi
    d.guncelle(ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24"))
    assert d.adimlar[0].hata_duzeltildi and d.adimlar[0].tamamlandi


def test_durum_kilit_ve_israr():
    s = senaryo_ile(adim1={"durum": "kilitli"},
                    persona={"davranis": "israrci", "israr_sayisi": 1, "israr_taktikleri": ["yalvarma"]})
    d = OgrenciDurumu.baslat(s)
    assert d.siradaki_taktik == "yalvarma" and d.israr_kalan == 1
    d.guncelle(ogr_js(israr_taktigi="yalvarma", mesaj="lütfen"))
    assert d.israr_kalan == 0 and d.siradaki_taktik is None
    d.guncelle(ogr_js(denenen_adim=1, kilit_acildi=True, mesaj="anladım galiba"))
    assert d.adimlar[0].kilit_acildi and any(o["olay"] == "kilit_acildi_ogrenci_beyani" for o in d.olaylar)


def test_durum_cozumlu_tahmin_tamamlamaz():
    d = OgrenciDurumu.baslat(senaryo_ile())
    d.guncelle(ogr_js(denenen_adim=1, verilen_deger=24, tahmin_listesi=[24, 30], mesaj="24 mü 30 mu"))
    assert not d.adimlar[0].tamamlandi


def test_durum_ozet_adimi_kapanir():
    s = senaryo_ile()
    s["adimlar"].append({"no": 3, "alt_soru_tr": "Toplam kaç?", "deger": None, "durum": "biliyor"})
    d = OgrenciDurumu.baslat(s)
    d.guncelle(ogr_js(denenen_adim=1, verilen_deger=24, mesaj="24"))
    d.guncelle(ogr_js(denenen_adim=2, verilen_deger=72, mesaj="72"))
    assert d.son_cevap_verildi and d.adimlar[2].dogrulanamadi


def test_durum_acilis_kontrol_isteyen():
    s = senaryo_ile(persona={"acilis": "kontrol_isteyen"}, acilis_mesaji="72 buldum doğru mu", acilis_verilen_deger=72)
    d = OgrenciDurumu.baslat(s)
    assert d.son_cevap_verildi and d.aktif_adim == 3


def test_durum_acilis_yanlis_denemeli():
    s = senaryo_ile(persona={"acilis": "yanlis_denemeli"}, bilgi_sablonu="bir_hatali",
                    adim2={"durum": "hatali", "hata_tipi": "islem_hatasi"},
                    acilis_mesaji="mayısta 24 buldum toplamı 70 buldum", acilis_verilen_deger=70)
    d = OgrenciDurumu.baslat(s)
    assert d.adimlar[0].tamamlandi and d.aktif_adim == 2 and d.adimlar[1].yanlis_deneme == 1


# ================================================================== senaryo
def _soru(n_adim: int, i: int = 0) -> dict:
    return {"id": f"gsm8k_train_{i}", "soru_tr": "soru", "son_cevap": 9.0, "soru_sayilari": [1.0],
            "adimlar": [{"no": k, "alt_soru_tr": f"a{k}", "deger": float(k), "alt_soru_en": ""} for k in range(1, n_adim + 1)]}


def test_uyumluluk_kurallari(cfg):
    assert uyumluluk_ihlali("hepsi_biliyor", "yanlis_denemeli", "isbirlikci")
    assert uyumluluk_ihlali("bir_kilitli", "kontrol_isteyen", "isbirlikci")
    assert uyumluluk_ihlali("hepsi_biliyor", "kopyala_yapistir", "kaygili")
    assert uyumluluk_ihlali("bir_hatali", "yanlis_denemeli", "kaygili") is None
    senaryolar = [s for i in range(400) for s in soru_senaryolari(_soru(2 + i % 4, i), cfg)]
    for s in senaryolar:
        p, sablon = s["persona"], s["bilgi_sablonu"]
        assert not (p["acilis"] == "yanlis_denemeli" and sablon == "hepsi_biliyor")
        assert not (p["acilis"] == "kontrol_isteyen" and sablon not in ("hepsi_biliyor", "bir_hatali"))
        assert not (sablon == "hepsi_biliyor" and p["davranis"] == "kaygili")
        if sablon == "hatali_ve_kilitli":
            assert len(s["adimlar"]) >= 3
        if p["acilis"] == "yanlis_denemeli":
            h = [a["no"] for a in s["adimlar"] if a["durum"] == "hatali"]
            k = [a["no"] for a in s["adimlar"] if a["durum"] == "kilitli"]
            assert h and (not k or min(h) < min(k))
        if p["davranis"] == "israrci":
            t = p["israr_taktikleri"]
            assert len(t) == p["israr_sayisi"] and t == sorted(t, key=cfg["israr_taktikleri"].index)
        assert sum(a["durum"] == "hatali" for a in s["adimlar"]) == (1 if sablon in ("bir_hatali", "hatali_ve_kilitli") else 0)


def test_degersiz_adim_hatali_olmaz(cfg):
    soru = _soru(3)
    soru["adimlar"][0]["deger"] = None
    for i in range(30):
        soru["id"] = f"gsm8k_train_{i}"
        for s in soru_senaryolari(soru, cfg):
            assert s["adimlar"][0]["durum"] == "biliyor"


def test_ortak_dagilim_marjinalleri(cfg):
    d = ortak_dagilim(cfg)
    marj = Counter()
    for (s, a, v), p in d.items():
        marj[a] += p
    for a, hedef in cfg["acilis_oranlari"].items():
        assert abs(marj[a] - hedef) < 0.01


def test_senaryo_belirlenimci(cfg):
    assert soru_senaryolari(_soru(3), cfg) == soru_senaryolari(_soru(3), cfg)


# ================================================================== rol çevirme ve istemler
def test_rol_cevirme_ve_iz_yok():
    m = [Mesaj("ogrenci", "soru"), Mesaj("ogretmen", "ipucu", iz="GİZLİ İZ 72"), Mesaj("ogrenci", "24")]
    og = ogretmene_gecmis(m)
    assert [x["role"] for x in og] == ["user", "assistant", "user"]
    ogr = ogrenciye_gecmis(m)
    assert [x["role"] for x in ogr] == ["assistant", "user", "assistant"]
    for gecmis in (og, ogr):
        assert all(set(x) == {"role", "content"} for x in gecmis)
        assert "GİZLİ" not in str(gecmis)


def test_ogrenci_isteminde_deger_yok(cfg):
    ist = Istemler.yukle(cfg)
    s = senaryo_ile(adim1={"durum": "hatali", "hata_tipi": "islem_hatasi"})
    metin = ist.ogrenci_tur_istemi(s, OgrenciDurumu.baslat(s))
    assert "24" not in metin and "72" not in metin and "{" not in metin.split("ÇIKTI")[0]
    assert "Natalia mayıs ayında" in metin


def test_ogretmen_isteminde_senaryo_yok(cfg):
    ist = Istemler.yukle(cfg)
    assert "TASLAK" not in ist.ogretmen_sistem
    for yasak in ("72", "Natalia", "hatali", "israrci", "Türkçe"):
        assert yasak not in ist.ogretmen_sistem


def test_acilis_istemi_dallanma(cfg):
    ist = Istemler.yukle(cfg)
    s = senaryo_ile(persona={"acilis": "yanlis_denemeli"}, adim1={"durum": "hatali", "hata_tipi": "birim_hatasi"})
    metin = ist.acilis_istemi(s)
    assert "24" not in metin and "72" not in metin and "Birimleri karıştırırsın" in metin
    metin2 = ist.acilis_istemi(senaryo_ile(persona={"acilis": "kontrol_isteyen"}))
    assert "72" in metin2  # hepsi_biliyor: son cevap verilir
    assert "72" not in ist.acilis_istemi(senaryo_ile(persona={"acilis": "kopyala_yapistir"}))


def test_acilis_birlestir_soru_birebir():
    s = NATALIA_SENARYO["soru_tr"]
    assert acilis_birlestir({"on_ek": "selam", "son_ek": "cevabı ne"}, s) == f"selam {s} cevabı ne"
    assert acilis_birlestir({"on_ek": "", "son_ek": ""}, s) == s


# ================================================================== istemci yardımcıları
def test_iz_ayir_ve_json_coz():
    class M:
        content = "<think>düşündüm</think>cevap"
        reasoning_content = None
        model_extra = {}
    assert iz_ayir(M()) == ("düşündüm", "cevap")

    class M2:
        content = "cevap"
        reasoning_content = None
        model_extra = {"reasoning": "iz"}
    assert iz_ayir(M2()) == ("iz", "cevap")
    assert json_coz('```json\n{"a": 1}\n```') == ({"a": 1}, None)
    assert json_coz("bozuk")[0] is None


# ================================================================== sahte istemciyle tam diyalog
def test_sahte_diyalog_bitiyor(cfg):
    cfg2 = copy.deepcopy(cfg)
    cfg2["sahte"] = {"ogretmen_hata_orani": 0.0, "ogrenci_hata_orani": 0.0}
    loglar = []
    s = senaryo_ile()
    sonuc = asyncio.run(diyalog_calistir(s, SahteIstemci(cfg2), Hakem.yukle(cfg), Istemler.yukle(cfg),
                                         DiyalogAyar(), loglar.append, "test"))
    assert sonuc.durum == "kaydedildi" and sonuc.bitis == "cozuldu"
    assert sonuc.mesajlar[0].rol == "ogrenci" and sonuc.mesajlar[-1].rol == "ogretmen"
    assert all(m.iz for m in sonuc.mesajlar if m.rol == "ogretmen")
    assert loglar and {"baglam_uzunlugu", "sorunlar", "kabul", "calisma_id"} <= set(loglar[0])
