from conftest import NATALIA_EN

from src.gsm8k import kayma_bul, socratic_ayristir
from src.sayilar import (bicimle, esit, etiket_sonuclari, icinde, kume_esit, sayi_ayristir, sayilari_cikar,
                         tokenlar)


# ------------------------------------------------------------------ socratic ayrıştırma
def test_natalia_socratic():
    adimlar, son = socratic_ayristir(NATALIA_EN, "en")
    assert len(adimlar) == 2
    assert [a["deger"] for a in adimlar] == [24.0, 72.0]
    assert son == 72.0
    assert adimlar[0]["alt_soru"] == "How many clips did Natalia sell in May?"
    assert adimlar[1]["aciklama"].startswith("Natalia sold 48+24")


def test_etiketsiz_adim_null():
    adimlar, son = socratic_ayristir("Q1? ** a = <<2*3=6>>6\nQ2? ** Therefore 6.\n#### 6", "en")
    assert adimlar[1]["deger"] is None and son == 6.0


def test_son_etiket_alinir():
    assert etiket_sonuclari("x <<2+3=5>>5 ve <<5*2=10>>10") == [5.0, 10.0]
    adimlar, _ = socratic_ayristir("Q? ** <<2+3=5>>5 then <<5*2=10>>10\n#### 10")
    assert adimlar[0]["deger"] == 10.0


def test_son_cevap_ayristirilamaz():
    assert socratic_ayristir("Q? ** a <<1+1=2>>2\n#### iki", "en")[1] is None
    assert socratic_ayristir("Q? ** a <<1+1=2>>2\n#### 1,600", "en")[1] == 1600.0


def test_tr_etiket_virgullu_ondalik():
    assert etiket_sonuclari("<<12/60=0,2>>0,2", "tr") == [0.2]


def test_kayma_bulunur():
    en = [{"answer": f"#### {i}"} for i in range(10)]
    tr = [{"answer": f"#### {i}"} for i in range(1, 10)]
    assert kayma_bul(en, tr)[0] == 1


# ------------------------------------------------------------------ sayılar
def test_ingilizce_binlik_ondalik():
    assert sayilari_cikar("It costs $1,200 and 0.5 kg, 25%", "en", genis=False) == [1200.0, 0.5, 25.0]
    assert sayilari_cikar("rate of .5 inches", "en") == [0.5]


def test_turkce_binlik_ondalik():
    assert sayilari_cikar("1.200 TL ve 0,5 kg", "tr", genis=False) == [1200.0, 0.5]
    assert sayilari_cikar("1 200 kişi geldi", "tr", genis=False) == [1200.0]
    # çeviride korunmuş İngilizce ondalık
    assert sayilari_cikar("1.5 saat", "tr") == [1.5]


def test_belirsiz_bicim_adaylari():
    t = tokenlar("1.250 lira", "tr")[0]
    assert t.birincil == 1250.0 and icinde(1.25, t.adaylar)
    assert icinde(1.25, sayilari_cikar("1.250", "auto")) and icinde(1250, sayilari_cikar("1.250", "auto"))


def test_kesir_hem_kesir_hem_parcalar():
    s = sayilari_cikar("3/4 kadarı", "tr")
    assert icinde(0.75, s) and icinde(3, s) and icinde(4, s)


def test_eksi_ve_cikarma():
    assert sayilari_cikar("fark -5 çıktı", "tr") == [-5.0]
    assert sayilari_cikar("48-24 = 24", "tr") == [48.0, 24.0]


def test_sira_sayisi_atlanir():
    assert sayilari_cikar("2. adımda 24 buldun", "tr", sira_atla=True) == [24.0]
    assert sayilari_cikar("2. adımda 24 buldun", "tr") == [2.0, 24.0]


def test_cumle_sonu_noktasi():
    assert sayilari_cikar("Sonuç 24. Sonra devam", "tr") == [24.0]


def test_toleransli_esitlik():
    assert esit(0.1 + 0.2, 0.3)
    assert esit(1_000_000, 1_000_050)       # göreli 1e-4 içinde
    assert not esit(24, 25)
    assert not esit(None, 1)


def test_kume_esit_en_tr():
    en = tokenlar("She sold 1,200 clips at $0.5 each.", "en")
    tr = tokenlar("Tanesi 0,5 dolardan 1.200 toka sattı.", "tr")
    assert kume_esit(en, tr)
    assert not kume_esit(en, tokenlar("Tanesi 0,5 dolardan 1.300 toka sattı.", "tr"))


def test_tek_sayi_ve_bicimle():
    assert sayi_ayristir("72") == 72.0
    assert sayi_ayristir("72 ve 5") is None
    assert bicimle(72.0) == "72" and bicimle(0.2) == "0,2" and bicimle(0.2, "en") == "0.2"
