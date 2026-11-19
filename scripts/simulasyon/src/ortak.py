"""Betiklerin ortak kullandığı yardımcılar: yapılandırma, JSONL, istem dosyaları, tohumlama."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import yaml

KOK = Path(__file__).resolve().parent.parent  # simulasyon/


# ---------------------------------------------------------------- yapılandırma
def config_yukle(yol: str | Path | None = None) -> dict:
    """config.yaml'ı okur; dizinleri mutlak yola çevirip `_yollar` altına koyar."""
    yol = Path(yol) if yol else KOK / "config.yaml"
    with open(yol, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    taban = yol.resolve().parent
    diz = cfg.get("dizinler", {})

    def coz(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else taban / p

    veri, log, istem = coz(diz.get("veri", "veri")), coz(diz.get("log", "loglar")), coz(diz.get("istem", "istemler"))
    veri.mkdir(parents=True, exist_ok=True)
    log.mkdir(parents=True, exist_ok=True)
    cfg["_yollar"] = {
        "taban": taban, "veri": veri, "log": log, "istem": istem,
        "sorular_train": veri / "sorular_train.jsonl",
        "sorular_test": veri / "sorular_test.jsonl",
        "elenen_sorular": veri / "elenen_sorular.jsonl",
        "senaryolar": veri / "senaryolar.jsonl",
        "senaryolar_acilisli": veri / "senaryolar_acilisli.jsonl",
        "atilan_senaryolar": veri / "atilan_senaryolar.jsonl",
        "ham_diyaloglar": veri / "ham_diyaloglar.jsonl",
        "atilan_diyaloglar": veri / "atilan_diyaloglar.jsonl",
        "sft": veri / "sft.jsonl",
        "dpo_adaylari": veri / "dpo_adaylari.jsonl",
        "denemeler": log / "denemeler.jsonl",
        "acilis_denemeleri": log / "acilis_denemeleri.jsonl",
        "pilot_rapor": log / "pilot_rapor.md",
    }
    return cfg


def istem_yolu(cfg: dict, anahtar: str) -> Path:
    return cfg["_yollar"]["istem"] / cfg["istemler"][anahtar]


# ---------------------------------------------------------------- JSONL
def jsonl_oku(yol: str | Path) -> list[dict]:
    """JSONL okur. Yarım kalmış (bozuk) son satırı uyarıyla atlar."""
    yol = Path(yol)
    if not yol.exists():
        return []
    kayitlar = []
    with open(yol, encoding="utf-8") as f:
        satirlar = f.readlines()
    for i, s in enumerate(satirlar):
        s = s.strip()
        if not s:
            continue
        try:
            kayitlar.append(json.loads(s))
        except json.JSONDecodeError:
            print(f"UYARI: {yol.name} satır {i + 1} okunamadı, atlandı.", file=sys.stderr)
    return kayitlar


def jsonl_ekle(yol: str | Path, kayit: dict) -> None:
    """Tek kaydı ekleme modunda yazar ve hemen diske boşaltır."""
    with open(yol, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False, default=_json_varsayilan) + "\n")
        f.flush()


def _json_varsayilan(o):
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"JSON'a çevrilemez: {type(o)}")


def mevcut_idler(*yollar: str | Path) -> set[str]:
    idler: set[str] = set()
    for y in yollar:
        for k in jsonl_oku(y):
            if "id" in k:
                idler.add(k["id"])
    return idler


# ---------------------------------------------------------------- istemler
_YORUM_RE = re.compile(r"<!--.*?-->\s*", re.S)


def istem_oku(yol: str | Path) -> str:
    """İstem dosyasını okur; HTML yorumlarını (<!-- TASLAK ... -->) modele göndermemek için siler."""
    metin = Path(yol).read_text(encoding="utf-8")
    return _YORUM_RE.sub("", metin).strip()


def sablon_doldur(sablon: str, alanlar: dict) -> str:
    """Yalnızca bilinen {alan} yer tutucularını değiştirir; JSON örneklerindeki süslü parantezlere dokunmaz."""
    def degistir(m):
        ad = m.group(1)
        return str(alanlar[ad]) if ad in alanlar else m.group(0)
    return re.sub(r"\{(\w+)\}", degistir, sablon)


def dosya_hash(yol: str | Path) -> str:
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()[:16]


def istem_surumleri(cfg: dict) -> dict:
    return {ad: {"dosya": dosya, "hash": dosya_hash(cfg["_yollar"]["istem"] / dosya)}
            for ad, dosya in cfg["istemler"].items()}


def yaml_oku(yol: str | Path) -> dict:
    with open(yol, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------- rastgelelik / zaman
def rng(seed, *parcalar) -> random.Random:
    """Parçalara göre belirlenimci RNG: kaldığı yerden devam edince aynı sonuçlar üretilir."""
    return random.Random("|".join(str(p) for p in (seed, *parcalar)))


def istek_seed(seed, *parcalar) -> int:
    h = hashlib.sha256("|".join(str(p) for p in (seed, *parcalar)).encode()).hexdigest()
    return int(h[:8], 16) % (2**31)


def agirlikli_sec(r: random.Random, oranlar: dict, izinli: set | None = None):
    secenekler = [(k, v) for k, v in oranlar.items() if v > 0 and (izinli is None or k in izinli)]
    if not secenekler:
        return None
    toplam = sum(v for _, v in secenekler)
    x = r.random() * toplam
    for k, v in secenekler:
        x -= v
        if x <= 0:
            return k
    return secenekler[-1][0]


def simdi() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def tr_kucuk(s: str) -> str:
    """Türkçe kurallarıyla küçük harf (I→ı, İ→i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()
