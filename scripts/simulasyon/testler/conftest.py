import copy
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from src.diyalog import Mesaj  # noqa: E402
from src.durum import OgrenciDurumu  # noqa: E402
from src.hakem import Hakem  # noqa: E402
from src.ortak import config_yukle  # noqa: E402

NATALIA_EN = (
    "How many clips did Natalia sell in May? ** Natalia sold 48/2 = <<48/2=24>>24 clips in May.\n"
    "How many clips did Natalia sell altogether in April and May? ** Natalia sold 48+24 = <<48+24=72>>72 clips "
    "altogether in April and May.\n#### 72"
)

NATALIA_SENARYO = {
    "id": "gsm8k_train_0__s0",
    "soru_id": "gsm8k_train_0",
    "soru_tr": "Natalia nisan ayında 48 arkadaşına toka sattı, mayıs ayında ise bunun yarısı kadar toka sattı. "
               "Natalia nisan ve mayıs aylarında toplam kaç toka sattı?",
    "adimlar": [
        {"no": 1, "alt_soru_tr": "Natalia mayıs ayında kaç toka sattı?", "deger": 24.0, "durum": "biliyor"},
        {"no": 2, "alt_soru_tr": "Natalia nisan ve mayıs aylarında toplam kaç toka sattı?", "deger": 72.0,
         "durum": "biliyor"},
    ],
    "son_cevap": 72.0,
    "soru_sayilari": [48.0],
    "bilgi_sablonu": "hepsi_biliyor",
    "persona": {"acilis": "kopyala_yapistir", "davranis": "isbirlikci", "israr_sayisi": 0, "israr_taktikleri": []},
    "uslup": {"yazim": "duzgun", "baglam": "yok", "ton": "kibar"},
    "acilis_mesaji": "Natalia nisan ayında 48 arkadaşına toka sattı, mayıs ayında ise bunun yarısı kadar toka sattı. "
                     "Natalia nisan ve mayıs aylarında toplam kaç toka sattı? cevabı ne",
}


@pytest.fixture(scope="session")
def cfg():
    return config_yukle(KOK / "config.yaml")


@pytest.fixture(scope="session")
def hakem(cfg):
    return Hakem.yukle(cfg)


@pytest.fixture
def senaryo():
    return copy.deepcopy(NATALIA_SENARYO)


def senaryo_ile(**degisiklik):
    """Natalia senaryosunu değiştirerek kopyalar. adim1/adim2 = durum sözlüğü güncellemesi."""
    s = copy.deepcopy(NATALIA_SENARYO)
    for k in ("adim1", "adim2"):
        if k in degisiklik:
            s["adimlar"][int(k[-1]) - 1].update(degisiklik.pop(k))
    if "persona" in degisiklik:
        s["persona"].update(degisiklik.pop("persona"))
    if "uslup" in degisiklik:
        s["uslup"].update(degisiklik.pop("uslup"))
    s.update(degisiklik)
    return s


def ogr_js(**kw):
    js = {"denenen_adim": None, "verilen_deger": None, "kilit_acildi": False, "israr_taktigi": None,
          "tahmin_listesi": None, "kapatmak_istiyor": False, "mesaj": "bilmiyorum nereden başlayacağım"}
    js.update(kw)
    return js


def baslangic(senaryo):
    """(mesajlar, durum): açılış + ilk öğretmen mesajı."""
    mesajlar = [Mesaj("ogrenci", senaryo["acilis_mesaji"]),
                Mesaj("ogretmen", "Önce mayıs ayında kaç toka sattığını bulalım, bunun için ne yaparsın?", iz="...")]
    return mesajlar, OgrenciDurumu.baslat(senaryo)
