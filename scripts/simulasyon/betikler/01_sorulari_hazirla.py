#!/usr/bin/env python3
"""GSM8K socratic (EN) + GSM8K-TR socratic'i eşler, ayrıştırır, eler.

Çıktı: veri/sorular_train.jsonl, veri/sorular_test.jsonl, veri/elenen_sorular.jsonl
Test bölümü yalnızca ayrı dosyaya yazılır; sonraki betikler onu okumaz.

Önemli: malhajar/gsm8k-tr'de EN'nin ilk satırı yok, bu yüzden TR[i] = EN[i+1]. Kayma her
bölüm için son cevap uyumuna bakılarak otomatik bulunur ve her satır ayrıca son cevapla doğrulanır.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gsm8k import kayma_bul, socratic_ayristir, son_cevaplar_uyumlu  # noqa: E402
from src.ortak import config_yukle, jsonl_ekle, jsonl_oku, mevcut_idler  # noqa: E402
from src.sayilar import benzersiz, esit, kume_esit, tokenlar  # noqa: E402

BOLUMLER = ("train", "test")


def kaynak_yukle(cfg: dict, yerel_dizin: str | None) -> dict[str, tuple[list[dict], list[dict]]]:
    """{bolum: (en_satirlar, tr_satirlar)}. yerel_dizin verilirse {en,tr}_{train,test}.jsonl okunur."""
    if yerel_dizin:
        d = Path(yerel_dizin)
        return {b: (jsonl_oku(d / f"en_{b}.jsonl"), jsonl_oku(d / f"tr_{b}.jsonl")) for b in BOLUMLER}
    from datasets import load_dataset
    en = load_dataset(cfg["kaynak"]["en"]["ad"], cfg["kaynak"]["en"]["config"])
    tr = load_dataset(cfg["kaynak"]["tr"]["ad"], cfg["kaynak"]["tr"]["config"])
    return {b: (list(en[b]), list(tr[b])) for b in BOLUMLER}


def soru_isle(en_i: int, bolum: str, en: dict, tr: dict) -> tuple[dict | None, str | None, list[str]]:
    """(kayit, eleme_nedeni, uyarilar)."""
    uyarilar: list[str] = []
    en_adim, en_son = socratic_ayristir(en["answer"], "en")
    tr_adim, _ = socratic_ayristir(tr["answer"], "tr")  # TR'den yalnızca alt sorular alınır
    if en_son is None:
        return None, "son_cevap_ayristirilamadi", uyarilar
    # VARSAYIM: ek eleme kuralı — EN/TR son cevapları uyuşmuyorsa satır eşlemesine güvenilmez.
    if not son_cevaplar_uyumlu(en["answer"], tr["answer"]):
        return None, "en_tr_son_cevap_farkli", uyarilar
    if len(en_adim) != len(tr_adim):
        return None, "adim_sayisi_farkli", uyarilar
    en_tok, tr_tok = tokenlar(en["question"], "en"), tokenlar(tr["question"], "tr")
    if not kume_esit(en_tok, tr_tok):
        return None, "sayi_kumesi_farkli", uyarilar
    if not en_adim:
        return None, "adim_yok", uyarilar

    son_deger = en_adim[-1]["deger"]
    # VARSAYIM: "uyarı olarak say, eleme" → kayıt tutulur, yalnızca uyarı listesine yazılır.
    if son_deger is None or not esit(son_deger, en_son):
        uyarilar.append("son_adim_son_cevaptan_farkli")
    degersiz = [a["no"] for a in en_adim if a["deger"] is None]
    if degersiz:
        uyarilar.append("degersiz_adim")

    kayit = {
        "id": f"gsm8k_{bolum}_{en_i}",
        "soru_en": en["question"],
        "soru_tr": tr["question"],
        "adimlar": [
            {"no": e["no"], "alt_soru_tr": t["alt_soru"], "alt_soru_en": e["alt_soru"], "deger": e["deger"]}
            for e, t in zip(en_adim, tr_adim)
        ],
        "son_cevap": en_son,
        # Değerler her zaman İngilizce sürümden alınır.
        "soru_sayilari": benzersiz([x for t in en_tok for x in t.adaylar]),
        "degersiz_adimlar": degersiz,
        "uyarilar": uyarilar,
    }
    return kayit, None, uyarilar


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--yerel-dizin", default=None,
                    help="İndirmek yerine {en,tr}_{train,test}.jsonl dosyalarını buradan oku (test/çevrimdışı)")
    ap.add_argument("--limit", type=int, default=None, help="Bölüm başına en fazla N EN satırı işle")
    args = ap.parse_args()

    cfg = config_yukle(args.config)
    y = cfg["_yollar"]
    kaynak = kaynak_yukle(cfg, args.yerel_dizin)
    hazir = mevcut_idler(y["sorular_train"], y["sorular_test"], y["elenen_sorular"])

    for bolum in BOLUMLER:
        en_s, tr_s = kaynak[bolum]
        kayma, oran = kayma_bul(en_s, tr_s)
        print(f"[{bolum}] EN={len(en_s)} TR={len(tr_s)}  bulunan kayma: TR[i] = EN[i{kayma:+d}]  "
              f"(örneklemde son cevap uyumu %{oran * 100:.1f})")
        if oran < 0.95:
            sys.exit(f"HATA: {bolum} bölümünde EN/TR eşlemesi bulunamadı (en iyi uyum %{oran * 100:.1f}). Durduruldu.")
        tr_by_en = {i + kayma: tr_s[i] for i in range(len(tr_s)) if 0 <= i + kayma < len(en_s)}
        cikti = y["sorular_train"] if bolum == "train" else y["sorular_test"]
        n = len(en_s) if args.limit is None else min(args.limit, len(en_s))
        for en_i in range(n):
            sid = f"gsm8k_{bolum}_{en_i}"
            if sid in hazir:
                continue
            tr = tr_by_en.get(en_i)
            if tr is None:
                jsonl_ekle(y["elenen_sorular"], {"id": sid, "bolum": bolum, "neden": "tr_karsiligi_yok"})
                continue
            kayit, neden, _ = soru_isle(en_i, bolum, en_s[en_i], tr)
            if kayit is None:
                jsonl_ekle(y["elenen_sorular"], {"id": sid, "bolum": bolum, "neden": neden,
                                                 "soru_en": en_s[en_i]["question"], "soru_tr": tr["question"]})
            else:
                jsonl_ekle(cikti, kayit)

    rapor(cfg)


def rapor(cfg: dict) -> None:
    y = cfg["_yollar"]
    elenen = jsonl_oku(y["elenen_sorular"])
    for bolum, yol in (("train", y["sorular_train"]), ("test", y["sorular_test"])):
        kayitlar = jsonl_oku(yol)
        el = [e for e in elenen if e.get("bolum") == bolum]
        toplam = len(kayitlar) + len(el)
        print(f"\n=== {bolum}: toplam {toplam}, kabul {len(kayitlar)}, elenen {len(el)} ===")
        for neden, c in Counter(e["neden"] for e in el).most_common():
            print(f"  elenen  {neden:<32} {c:>6}")
        uy = Counter(u for k in kayitlar for u in k.get("uyarilar", []))
        for u, c in uy.most_common():
            print(f"  uyarı   {u:<32} {c:>6}")
        dag = Counter(len(k["adimlar"]) for k in kayitlar)
        print("  adım sayısı dağılımı: " + ", ".join(f"{a}:{dag[a]}" for a in sorted(dag)))


if __name__ == "__main__":
    main()
