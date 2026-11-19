#!/usr/bin/env python3
"""Öğretmen–öğrenci diyaloglarını simüle eder.

Girdi : veri/senaryolar_acilisli.jsonl (ya da --senaryo-dosyasi)
Çıktı : veri/ham_diyaloglar.jsonl, veri/atilan_diyaloglar.jsonl, loglar/denemeler.jsonl

Örnekler:
  python betikler/03_simulasyon.py --limit 50
  python betikler/03_simulasyon.py --tek gsm8k_train_1__s0 --ayrintili
  python betikler/03_simulasyon.py --sahte --limit 20
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.diyalog import DiyalogAyar, diyalog_calistir  # noqa: E402
from src.hakem import Hakem  # noqa: E402
from src.istemler import Istemler  # noqa: E402
from src.llm_istemci import LLMIstemci, SahteIstemci  # noqa: E402
from src.ortak import config_yukle, istem_surumleri, jsonl_ekle, jsonl_oku, mevcut_idler  # noqa: E402


def diyalog_kaydi(sonuc, senaryo: dict, cfg: dict, istemci, surumler: dict, calisma_id: str) -> dict:
    return {
        "id": sonuc.id,
        "senaryo": senaryo,
        "bitis": sonuc.bitis,
        "mesajlar": [m.kayit() for m in sonuc.mesajlar],
        "ogrenci_durumu": sonuc.ogrenci_durumu,
        "olaylar": sonuc.olaylar,
        "istem_surumleri": surumler,
        "model": istemci.model,
        "ornekleme": {"ogretmen": cfg["ogretmen_ornekleme"], "ogrenci": cfg["ogrenci_ornekleme"],
                      "json_zorlama": getattr(istemci, "json_modu", None)},
        "calisma_id": calisma_id,
        "baslangic": sonuc.baslangic,
        "bitis_zamani": sonuc.bitis_zamani,
    }


async def calistir(args, cfg: dict) -> None:
    y = cfg["_yollar"]
    senaryolar = jsonl_oku(args.senaryo_dosyasi or y["senaryolar_acilisli"])
    if any("_test_" in s["id"] for s in senaryolar):
        sys.exit("HATA: test bölümünden senaryo var; test bölümü simülasyona girmez.")
    istemci = SahteIstemci(cfg) if args.sahte else LLMIstemci(cfg)
    hakem, istemler = Hakem.yukle(cfg), Istemler.yukle(cfg)
    surumler = istem_surumleri(cfg)
    ayar = DiyalogAyar(maks_ogretmen_turu=cfg["maks_ogretmen_turu"], deneme_sayisi=cfg.get("deneme_sayisi", 3),
                       seed=cfg["seed"])
    calisma_id = uuid.uuid4().hex[:12]

    # ---------------------------------------------------------------- tek diyalog (hata ayıklama)
    if args.tek:
        s = next((s for s in senaryolar if s["id"] == args.tek), None)
        if s is None:
            sys.exit(f"Senaryo bulunamadı: {args.tek}")
        # VARSAYIM: --tek bir hata ayıklama modudur; --kaydet verilmedikçe dosyalara yazmaz.
        log = (lambda k: jsonl_ekle(y["denemeler"], k)) if args.kaydet else (lambda k: None)
        sonuc = await diyalog_calistir(s, istemci, hakem, istemler, ayar, log, calisma_id,
                                       ekran=print if args.ayrintili else None)
        if args.kaydet and sonuc.durum == "kaydedildi":
            jsonl_ekle(y["ham_diyaloglar"], diyalog_kaydi(sonuc, s, cfg, istemci, surumler, calisma_id))
        print(f"\nSonuç: {sonuc.durum} bitiş={sonuc.bitis} neden={sonuc.neden} mesaj={len(sonuc.mesajlar)}")
        await istemci.kapat()
        return

    # ---------------------------------------------------------------- toplu
    hazir = mevcut_idler(y["ham_diyaloglar"], y["atilan_diyaloglar"])
    bekleyen = [s for s in senaryolar if s["id"] not in hazir]
    if args.limit:
        bekleyen = bekleyen[: args.limit]
    print(f"Senaryo: {len(senaryolar)}, hazır: {len(hazir)}, bu çalıştırmada: {len(bekleyen)}, "
          f"eşzamanlı: {cfg['eszamanli']}, çalışma: {calisma_id}")
    sem = asyncio.Semaphore(cfg["eszamanli"])
    sayac: Counter = Counter()
    t0 = time.monotonic()

    def log(kayit: dict) -> None:
        jsonl_ekle(y["denemeler"], kayit)

    async def bir(s: dict) -> None:
        async with sem:
            sonuc = await diyalog_calistir(s, istemci, hakem, istemler, ayar, log, calisma_id)
        if sonuc.durum == "kaydedildi":
            jsonl_ekle(y["ham_diyaloglar"], diyalog_kaydi(sonuc, s, cfg, istemci, surumler, calisma_id))
            sayac[sonuc.bitis] += 1
        elif sonuc.durum == "atildi":
            jsonl_ekle(y["atilan_diyaloglar"], {"id": sonuc.id, "neden": sonuc.neden, "calisma_id": calisma_id,
                                                "mesajlar": [m.kayit() for m in sonuc.mesajlar],
                                                "bilgi_sablonu": s["bilgi_sablonu"], "persona": s["persona"]})
            sayac["atildi:" + sonuc.neden] += 1
        else:
            sayac["ag_hatasi"] += 1  # dosyaya yazılmaz → sonraki çalıştırmada yeniden denenir
        n = sum(sayac.values())
        if n % 50 == 0:
            saat = (time.monotonic() - t0) / 3600
            print(f"  {n}/{len(bekleyen)}  {dict(sayac)}  ~{n / max(saat, 1e-9):.0f} diyalog/saat", flush=True)

    await asyncio.gather(*(bir(s) for s in bekleyen))
    await istemci.kapat()
    print(f"\nBitti: {dict(sayac)}  süre {time.monotonic() - t0:.1f} sn  istemci: {dict(istemci.istatistik)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--sahte", action="store_true", help="GPU'suz sahte istemci")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--senaryo-dosyasi", default=None)
    ap.add_argument("--tek", default=None, metavar="SENARYO_ID", help="Tek diyalog çalıştır")
    ap.add_argument("--ayrintili", action="store_true", help="--tek ile: her deneme, iz ve hakem kararı ekrana")
    ap.add_argument("--kaydet", action="store_true",
                    help="--tek ile: sonucu ve denemeleri de dosyalara yaz (varsayılan: yalnızca ekran)")
    args = ap.parse_args()
    asyncio.run(calistir(args, config_yukle(args.config)))


if __name__ == "__main__":
    main()
