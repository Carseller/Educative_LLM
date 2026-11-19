"""Senaryo (bilgi durumu + persona + üslup) üretimi. GPU gerekmez."""
from __future__ import annotations

import random

from .ortak import agirlikli_sec, rng

ADIM_DURUMLARI = ("biliyor", "hatali", "kilitli")


def sablon_uygun_mu(sablon: str, adimlar: list[dict]) -> bool:
    """Bu sorunun adımları bu bilgi şablonunu taşıyabilir mi?

    VARSAYIM: `hatali`/`kilitli` yalnızca değeri bilinen (etiketli) adımlara atanır; değeri null
    olan adımı hakem doğrulayamayacağı için bu adımlar hep `biliyor` kalır.
    """
    degerli = [a for a in adimlar if a.get("deger") is not None]
    if sablon == "hepsi_biliyor":
        return True
    if sablon in ("bir_hatali", "bir_kilitli"):
        return len(degerli) >= 1
    if sablon == "hatali_ve_kilitli":
        return len(adimlar) >= 3 and len(degerli) >= 2
    return False


def uyumluluk_ihlali(sablon: str, acilis: str, davranis: str, adimlar: list[dict] | None = None) -> str | None:
    """Kural ihlali varsa nedenini, yoksa None döndürür."""
    hatali_var = sablon in ("bir_hatali", "hatali_ve_kilitli")
    if acilis == "yanlis_denemeli" and not hatali_var:
        return "yanlis_denemeli_hatali_adim_yok"
    if acilis == "kontrol_isteyen" and sablon not in ("hepsi_biliyor", "bir_hatali"):
        return "kontrol_isteyen_sablon_uyumsuz"
    if sablon == "hepsi_biliyor" and davranis == "kaygili":
        return "hepsi_biliyor_kaygili"
    if adimlar is not None:
        hatali = [a["no"] for a in adimlar if a.get("durum") == "hatali"]
        kilitli = [a["no"] for a in adimlar if a.get("durum") == "kilitli"]
        # VARSAYIM: yanlış denemeli açılışta öğrenci hatalı adıma kadar çalışmasını gösterir;
        # kilitli adım hatalı adımdan önce gelirse bu mümkün olmaz.
        if acilis == "yanlis_denemeli" and hatali and kilitli and min(kilitli) < min(hatali):
            return "kilitli_hataliden_once"
    return None


def _adimlari_ata(r: random.Random, sablon: str, adimlar: list[dict], acilis: str, hata_tipleri: list[str]) -> list[dict]:
    degerli = [a["no"] for a in adimlar if a.get("deger") is not None]
    durumlar = {a["no"]: "biliyor" for a in adimlar}
    if sablon == "bir_hatali":
        durumlar[r.choice(degerli)] = "hatali"
    elif sablon == "bir_kilitli":
        durumlar[r.choice(degerli)] = "kilitli"
    elif sablon == "hatali_ve_kilitli":
        h, k = r.sample(degerli, 2)
        if acilis == "yanlis_denemeli" and k < h:
            h, k = k, h
        durumlar[h], durumlar[k] = "hatali", "kilitli"
    cikti = []
    for a in adimlar:
        y = {"no": a["no"], "alt_soru_tr": a["alt_soru_tr"], "deger": a["deger"], "durum": durumlar[a["no"]]}
        if y["durum"] == "hatali":
            y["hata_tipi"] = r.choice(hata_tipleri)
        cikti.append(y)
    return cikti


def _persona(r: random.Random, acilis: str, davranis: str, cfg: dict) -> dict:
    p = {"acilis": acilis, "davranis": davranis, "israr_sayisi": 0, "israr_taktikleri": []}
    if davranis == "israrci":
        n = r.choice(cfg["israr_sayilari"])
        katalog = cfg["israr_taktikleri"]
        # VARSAYIM: "listeden sırayla seçilmiş" = rastgele n taktik, listedeki sıralarına göre dizilmiş.
        secilen = sorted(r.sample(katalog, n), key=katalog.index)
        p.update(israr_sayisi=n, israr_taktikleri=secilen)
    return p


def ortak_dagilim(cfg: dict, tur: int = 500) -> dict[tuple[str, str, str], float]:
    """Uyumlu (şablon, açılış, davranış) üçlüleri üzerinde, marjinalleri config oranlarına uyan dağılım.

    Bağımsız örnekleyip uyumsuzları atmak marjinalleri bozar (ör. yanlis_denemeli yalnızca hatalı
    şablonlarla eşleşebildiği için bir_hatali şişer). Bunun yerine uyumlu üçlüler üzerinde iteratif
    orantılı uydurma (IPF) yapılır: her eksenin marjinali sırayla hedefe ölçeklenir.
    """
    hedef = [cfg["bilgi_sablonu_oranlari"], cfg["acilis_oranlari"], cfg["davranis_oranlari"]]
    hedef = [{k: v / sum(h.values()) for k, v in h.items() if v > 0} for h in hedef]
    w = {(s, a, d): 1.0 for s in hedef[0] for a in hedef[1] for d in hedef[2]
         if uyumluluk_ihlali(s, a, d) is None}
    for _ in range(tur):
        for eksen in range(3):
            marj: dict[str, float] = {}
            for k, v in w.items():
                marj[k[eksen]] = marj.get(k[eksen], 0.0) + v
            for k in w:
                if marj[k[eksen]] > 0:
                    w[k] *= hedef[eksen][k[eksen]] / marj[k[eksen]]
    toplam = sum(w.values())
    return {k: v / toplam for k, v in w.items()}


_DAGILIM_ONBELLEK: dict = {}


def _dagilim(cfg: dict) -> dict:
    anahtar = repr((cfg["bilgi_sablonu_oranlari"], cfg["acilis_oranlari"], cfg["davranis_oranlari"]))
    if anahtar not in _DAGILIM_ONBELLEK:
        _DAGILIM_ONBELLEK[anahtar] = ortak_dagilim(cfg)
    return _DAGILIM_ONBELLEK[anahtar]


def _aday(r: random.Random, soru: dict, cfg: dict, haric: set | None = None) -> dict | None:
    dag = {k: v for k, v in _dagilim(cfg).items()
           if sablon_uygun_mu(k[0], soru["adimlar"]) and (not haric or k not in haric)}
    if not dag:
        return None
    sablon, acilis, davranis = agirlikli_sec(r, dag)
    adimlar = _adimlari_ata(r, sablon, soru["adimlar"], acilis, cfg["hata_tipleri"])
    if uyumluluk_ihlali(sablon, acilis, davranis, adimlar):  # güvenlik ağı; normalde olmaz
        return None
    u = cfg["uslup"]
    return {
        "soru_id": soru["id"],
        "soru_tr": soru["soru_tr"],
        "adimlar": adimlar,
        "son_cevap": soru["son_cevap"],
        "soru_sayilari": soru["soru_sayilari"],
        "bilgi_sablonu": sablon,
        "persona": _persona(r, acilis, davranis, cfg),
        "uslup": {"yazim": r.choice(u["yazim"]), "baglam": r.choice(u["baglam"]), "ton": r.choice(u["ton"])},
        "acilis_mesaji": None,
    }


def soru_senaryolari(soru: dict, cfg: dict) -> list[dict]:
    """Bir soru için `senaryo_per_soru` senaryo. Aynı soruda (şablon, açılış, davranış) tekrarından kaçınır."""
    r = rng(cfg["seed"], soru["id"], "senaryo")
    gorulen: set = set()
    cikti = []
    for i in range(cfg["senaryo_per_soru"]):
        secilen = None
        for _ in range(50):
            secilen = _aday(r, soru, cfg, haric=gorulen) or _aday(r, soru, cfg)
            if secilen is not None:
                break
        if secilen is None:
            continue
        gorulen.add((secilen["bilgi_sablonu"], secilen["persona"]["acilis"], secilen["persona"]["davranis"]))
        cikti.append({"id": f"{soru['id']}__s{i}", **secilen})
    return cikti
