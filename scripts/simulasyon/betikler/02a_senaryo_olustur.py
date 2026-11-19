#!/usr/bin/env python3
"""Her soru için senaryolar üretir (GPU gerekmez).

Girdi : veri/sorular_train.jsonl  (test bölümü OKUNMAZ)
Çıktı : veri/senaryolar.jsonl
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ortak import config_yukle, jsonl_ekle, jsonl_oku, mevcut_idler  # noqa: E402
from src.senaryo import soru_senaryolari  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--limit", type=int, default=None, help="Yalnızca ilk N soru")
    args = ap.parse_args()
    cfg = config_yukle(args.config)
    y = cfg["_yollar"]

    sorular = jsonl_oku(y["sorular_train"])
    if any("_test_" in s["id"] for s in sorular):
        sys.exit("HATA: girdide test bölümü sorusu var; test bölümü simülasyona girmez.")
    if args.limit:
        sorular = sorular[: args.limit]
    hazir = mevcut_idler(y["senaryolar"])
    yeni = 0
    for soru in sorular:
        for s in soru_senaryolari(soru, cfg):
            if s["id"] in hazir:
                continue
            jsonl_ekle(y["senaryolar"], s)
            yeni += 1
    print(f"Yeni senaryo: {yeni}")
    rapor(cfg, jsonl_oku(y["senaryolar"]))


def rapor(cfg: dict, senaryolar: list[dict]) -> None:
    n = len(senaryolar)
    print(f"\nToplam senaryo: {n}")
    if not n:
        return

    def tablo(baslik: str, sayac: Counter, oranlar: dict | None) -> None:
        print(f"\n{baslik:<24} {'adet':>7} {'pay':>7} {'config':>7}")
        for k in (oranlar or dict(sayac)):
            p = sayac[k] / n
            hedef = f"{oranlar[k]:.2f}" if oranlar else ""
            print(f"  {k:<22} {sayac[k]:>7} {p:>7.2f} {hedef:>7}")

    tablo("bilgi_sablonu", Counter(s["bilgi_sablonu"] for s in senaryolar), cfg["bilgi_sablonu_oranlari"])
    tablo("acilis", Counter(s["persona"]["acilis"] for s in senaryolar), cfg["acilis_oranlari"])
    tablo("davranis", Counter(s["persona"]["davranis"] for s in senaryolar), cfg["davranis_oranlari"])
    tablo("hata_tipi", Counter(a["hata_tipi"] for s in senaryolar for a in s["adimlar"] if a["durum"] == "hatali"), None)
    tablo("israr_sayisi (israrci)", Counter(s["persona"]["israr_sayisi"] for s in senaryolar
                                            if s["persona"]["davranis"] == "israrci"), None)
    for alan in ("yazim", "baglam", "ton"):
        tablo(f"uslup.{alan}", Counter(s["uslup"][alan] for s in senaryolar), None)
    print("\nNot: uyumluluk kuralları, marjinalleri config'e uydurulmuş ortak dağılımla (IPF) uygulanır. "
          "Kalan sapma, 2 adımlı sorularda hatali_ve_kilitli şablonunun mümkün olmamasındandır.")


if __name__ == "__main__":
    main()
