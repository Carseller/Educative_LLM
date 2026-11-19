#!/usr/bin/env python3
"""Bölüm 3.3–3.4 doğrulaması: GSM8K (EN) ile GSM8K-TR socratic satırları eşleşiyor mu?

- Bulunan kaymayla 20 rastgele satırı yan yana basar (soru başı, son cevap, adım sayısı).
- TR hesap etiketlerinde virgüllü ondalık (ör. <<12/60=0,2>>) sayısını raporlar.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gsm8k import kayma_bul, socratic_ayristir, son_cevap_ham, son_cevaplar_uyumlu  # noqa: E402
from src.ortak import config_yukle, rng  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    cfg = config_yukle(args.config)
    from datasets import load_dataset
    en = load_dataset(cfg["kaynak"]["en"]["ad"], cfg["kaynak"]["en"]["config"])
    tr = load_dataset(cfg["kaynak"]["tr"]["ad"], cfg["kaynak"]["tr"]["config"])
    r = rng(cfg["seed"], "eslesme_dogrula")
    for bolum in ("train", "test"):
        E, T = list(en[bolum]), list(tr[bolum])
        print(f"\n##### {bolum}: EN={len(E)} TR={len(T)}")
        for k in (0, 1):
            ok = sum(son_cevaplar_uyumlu(E[i + k]["answer"], T[i]["answer"]) for i in range(len(T)) if i + k < len(E))
            print(f"  kayma {k}: son cevap uyumu {ok}/{len(T)}")
        kayma, oran = kayma_bul(E, T)
        print(f"  seçilen kayma: TR[i] = EN[i{kayma:+d}]")
        tum_uyum = sum(son_cevaplar_uyumlu(E[i + kayma]["answer"], T[i]["answer"])
                       for i in range(len(T)) if 0 <= i + kayma < len(E))
        print(f"  tüm satırlarda son cevap uyumu: {tum_uyum}/{len(T)}")
        for i in sorted(r.sample(range(len(T)), args.n)):
            e, t = E[i + kayma], T[i]
            ea, _ = socratic_ayristir(e["answer"], "en")
            ta, _ = socratic_ayristir(t["answer"], "tr")
            ok = son_cevaplar_uyumlu(e["answer"], t["answer"]) and len(ea) == len(ta)
            print(f"  {'OK ' if ok else 'XX '} TR{i:>5} ↔ EN{i + kayma:>5} | son {son_cevap_ham(e['answer']):>8} / "
                  f"{son_cevap_ham(t['answer']):>8} | adım {len(ea)}/{len(ta)} | {t['question'][:60]!r}")
        virgul = sum(bool(re.search(r"<<[^>]*=\d+,\d+>>", t["answer"])) for t in T)
        print(f"  TR'de virgüllü ondalık etiket sonucu içeren satır: {virgul}")


if __name__ == "__main__":
    main()
