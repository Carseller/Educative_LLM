#!/usr/bin/env python3
"""Her senaryo için öğrenci modeliyle (düşünme kapalı) açılış mesajı üretir.

Girdi : veri/senaryolar.jsonl
Çıktı : veri/senaryolar_acilisli.jsonl, veri/atilan_senaryolar.jsonl, loglar/acilis_denemeleri.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.hakem import Hakem  # noqa: E402
from src.istemler import Istemler, acilis_birlestir, acilis_semasi  # noqa: E402
from src.llm_istemci import AgHatasi, LLMIstemci, SahteIstemci  # noqa: E402
from src.ortak import (config_yukle, istek_seed, istem_surumleri, jsonl_ekle, jsonl_oku,  # noqa: E402
                       mevcut_idler, simdi, tr_kucuk)


async def acilis_uret(senaryo: dict, istemci, hakem: Hakem, istemler: Istemler, cfg: dict, calisma_id: str) -> dict:
    """{'durum': 'kabul'|'atildi'|'ag_hatasi', 'kayit': ...}"""
    sema = acilis_semasi(senaryo["persona"]["acilis"])
    istem = istemler.acilis_istemi(senaryo)
    son_sorunlar: list = []
    for deneme in range(cfg.get("deneme_sayisi", 3)):
        try:
            y = await istemci.ogrenci_json(None, [{"role": "user", "content": istem}], sema,
                                           seed=istek_seed(cfg["seed"], senaryo["id"], "acilis", deneme),
                                           sahte_baglam={"tur": "acilis", "senaryo": senaryo, "deneme": deneme})
        except AgHatasi as e:
            return {"durum": "ag_hatasi", "neden": str(e)[:300]}
        sorunlar = hakem.acilis_kontrol(y.js, senaryo)
        jsonl_ekle(cfg["_yollar"]["acilis_denemeleri"], {
            "senaryo_id": senaryo["id"], "calisma_id": calisma_id, "deneme": deneme, "kabul": not sorunlar,
            "sorunlar": list(sorunlar), "js": y.js, "ham": y.icerik if y.js is None else None,
            "ayristirma": y.json_hatasi, "ag_hatasi": y.ag_hatasi, "zaman": simdi()})
        son_sorunlar = list(sorunlar)
        if not sorunlar:
            js = y.js
            if senaryo["persona"]["acilis"] in ("kopyala_yapistir", "cevabi_ne"):
                mesaj, verilen = acilis_birlestir(js, senaryo["soru_tr"]), None
            else:
                mesaj, verilen = js["mesaj"], js.get("verilen_deger")
            return {"durum": "kabul", "kayit": {**senaryo, "acilis_mesaji": mesaj, "acilis_verilen_deger": verilen,
                                                 "acilis_ham": js, "acilis_deneme_sayisi": deneme + 1}}
    return {"durum": "atildi", "kayit": {**senaryo, "atilma_nedeni": "acilis_3_deneme", "son_sorunlar": son_sorunlar}}


async def calistir(args, cfg: dict) -> None:
    y = cfg["_yollar"]
    senaryolar = jsonl_oku(args.senaryo_dosyasi or y["senaryolar"])
    hazir = mevcut_idler(y["senaryolar_acilisli"], y["atilan_senaryolar"])
    bekleyen = [s for s in senaryolar if s["id"] not in hazir]
    if args.limit:
        bekleyen = bekleyen[: args.limit]
    print(f"Senaryo: {len(senaryolar)}, hazır: {len(hazir)}, bu çalıştırmada: {len(bekleyen)}")
    istemci = SahteIstemci(cfg) if args.sahte else LLMIstemci(cfg)
    hakem, istemler = Hakem.yukle(cfg), Istemler.yukle(cfg)
    surumler = istem_surumleri(cfg)
    calisma_id = uuid.uuid4().hex[:12]
    sem = asyncio.Semaphore(cfg["eszamanli"])
    sayac: Counter = Counter()

    async def bir(s: dict) -> None:
        async with sem:
            r = await acilis_uret(s, istemci, hakem, istemler, cfg, calisma_id)
        sayac[r["durum"]] += 1
        if r["durum"] == "kabul":
            jsonl_ekle(y["senaryolar_acilisli"], {**r["kayit"], "acilis_istem_surumleri": surumler,
                                                  "acilis_model": istemci.model})
        elif r["durum"] == "atildi":
            jsonl_ekle(y["atilan_senaryolar"], r["kayit"])
        toplam = sum(sayac.values())
        if toplam % 200 == 0:
            print(f"  {toplam}/{len(bekleyen)} {dict(sayac)}", flush=True)

    await asyncio.gather(*(bir(s) for s in bekleyen))
    await istemci.kapat()
    print(f"Bitti: {dict(sayac)}  (ag_hatasi olanlar sonraki çalıştırmada yeniden denenir)")


def cesitlilik_raporu(cfg: dict) -> None:
    kayitlar = jsonl_oku(cfg["_yollar"]["senaryolar_acilisli"])
    if not kayitlar:
        return
    baslar = Counter(" ".join(tr_kucuk(k["acilis_mesaji"]).split()[:4]) for k in kayitlar)
    ilk10 = baslar.most_common(10)
    pay = sum(c for _, c in ilk10) / len(kayitlar)
    print(f"\n=== Çeşitlilik: {len(kayitlar)} açılış, {len(baslar)} farklı ilk-4-kelime başlangıcı ===")
    for b, c in ilk10:
        print(f"  {c:>6}  {b}")
    print(f"En sık 10 başlangıcın payı: %{pay * 100:.1f}  (eşik %{cfg['cesitlilik_esik'] * 100:.0f})")
    if pay > cfg["cesitlilik_esik"]:
        print("UYARI: açılış çeşitliliği düşük; ogrenci_acilis istemini ya da örnekleme ayarlarını gözden geçirin.")
    atilan = jsonl_oku(cfg["_yollar"]["atilan_senaryolar"])
    if atilan:
        nedenler = Counter(n for a in atilan for n in a.get("son_sorunlar", []))
        print(f"Atılan senaryo: {len(atilan)}; son denemedeki sorunlar: {dict(nedenler.most_common())}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--sahte", action="store_true", help="GPU'suz sahte istemci")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--senaryo-dosyasi", default=None)
    args = ap.parse_args()
    cfg = config_yukle(args.config)
    asyncio.run(calistir(args, cfg))
    cesitlilik_raporu(cfg)


if __name__ == "__main__":
    main()
