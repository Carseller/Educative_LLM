#!/usr/bin/env python3
"""Ham diyalogları eğitim biçimine çevirir.

Çıktı: veri/sft.jsonl, veri/dpo_adaylari.jsonl
- Yalnızca bitis ∈ {cozuldu, ogrenci_kapatti} (--tur-siniri-dahil ile tur_siniri da).
- Varsayılan: öğretmen turu başına bir örnek; yalnızca SON asistan mesajında reasoning_content var.
  --tam-diyalog: diyalog başına tek örnek, bütün asistan mesajlarında iz.
- Sistem istemi EKLENMEZ (context distillation).
- DPO adayları: aynı bağlamda (aynı diyalog, aynı çalışma, aynı baglam_uzunlugu) reddedilmiş ve kabul
  edilmiş öğretmen denemesi çiftleri.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ortak import config_yukle, jsonl_ekle, jsonl_oku, mevcut_idler  # noqa: E402
from src.sayilar import bicimle  # noqa: E402


def kategori(senaryo: dict) -> str:
    """VARSAYIM: birden çok kural uyarsa talimattaki sıra önceliklidir."""
    p = senaryo["persona"]
    if p["acilis"] == "kontrol_isteyen":
        return "cozum_kontrolu"
    if p["davranis"] in ("israrci", "tahmin_avcisi"):
        return "manipulasyon"
    if senaryo["bilgi_sablonu"] == "bir_kilitli" or p["davranis"] == "kaygili":
        return "kademeli_destek"
    return "yonlendirme"


def anahtar_adim(senaryo: dict) -> str:
    for a in senaryo["adimlar"]:
        if a["durum"] in ("hatali", "kilitli"):
            return a["alt_soru_tr"]
    return senaryo["adimlar"][0]["alt_soru_tr"]


def _mesaj(m: dict, iz: bool) -> dict:
    if m["rol"] == "ogrenci":
        return {"role": "user", "content": m["icerik"]}
    d = {"role": "assistant", "content": m["icerik"]}
    if iz:
        d["reasoning_content"] = m.get("iz") or ""
    return d


def ust_bilgi(d: dict, ornek_id: str) -> dict:
    s = d["senaryo"]
    return {
        "id": ornek_id, "kategori": kategori(s), "ders": "matematik", "sinif": None, "zorluk": None,
        "ogrenci_tipi": s["persona"]["davranis"], "kaynak": "gsm8k_simulasyon",
        "dogru_cevap": bicimle(s["son_cevap"]),  # VARSAYIM: Türkçe biçim (ondalık virgül)
        "anahtar_adim": anahtar_adim(s),
        "rehber_surumu": Path(d["istem_surumleri"]["ogretmen_sistem"]["dosya"]).stem,
    }


def sft_ornekleri(d: dict, tam_diyalog: bool) -> list[dict]:
    mesajlar = d["mesajlar"]
    if tam_diyalog:
        return [{**ust_bilgi(d, f"{d['id']}__tam"), "messages": [_mesaj(m, iz=True) for m in mesajlar]}]
    ornekler = []
    k = 0
    for i, m in enumerate(mesajlar):
        if m["rol"] != "ogretmen":
            continue
        k += 1
        msgs = [_mesaj(x, iz=False) for x in mesajlar[:i]] + [_mesaj(m, iz=True)]
        ornekler.append({**ust_bilgi(d, f"{d['id']}__t{k}"), "messages": msgs})
    return ornekler


def dpo_adaylari(d: dict, denemeler: list[dict]) -> list[dict]:
    gruplar: dict[int, list[dict]] = defaultdict(list)
    for x in denemeler:
        gruplar[x["baglam_uzunlugu"]].append(x)
    cikti = []
    for baglam, dd in sorted(gruplar.items()):
        kabul = [x for x in dd if x["kabul"]]
        ret = [x for x in dd if not x["kabul"]]
        if not kabul or not ret:
            continue
        secilen = kabul[0]
        tur = secilen["ogretmen_tur"] + 1
        prompt = [_mesaj(m, iz=False) for m in d["mesajlar"][:baglam]]
        for r in ret:
            cikti.append({
                "id": f"{d['id']}__t{tur}__r{r['deneme']}",
                "kategori": kategori(d["senaryo"]),
                "prompt": prompt,
                "chosen": {"role": "assistant", "content": secilen["cevap"], "reasoning_content": secilen["iz"]},
                "rejected": {"role": "assistant", "content": r["cevap"], "reasoning_content": r["iz"]},
                "red_nedeni": r["sorunlar"],
            })
    return cikti


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--tur-siniri-dahil", action="store_true")
    ap.add_argument("--tam-diyalog", action="store_true")
    args = ap.parse_args()
    cfg = config_yukle(args.config)
    y = cfg["_yollar"]

    # VARSAYIM: DPO adayları da SFT ile aynı bitiş filtresinden geçer.
    izinli = {"cozuldu", "ogrenci_kapatti"} | ({"tur_siniri"} if args.tur_siniri_dahil else set())
    diyaloglar = [d for d in jsonl_oku(y["ham_diyaloglar"]) if d["bitis"] in izinli]
    # yalnızca bu diyalogların ait olduğu çalışmadaki öğretmen denemeleri
    istenen = {(d["id"], d.get("calisma_id")) for d in diyaloglar}
    denemeler: dict[tuple, list] = defaultdict(list)
    for x in jsonl_oku(y["denemeler"]):
        if x["rol"] == "ogretmen" and (x["diyalog_id"], x.get("calisma_id")) in istenen:
            denemeler[(x["diyalog_id"], x.get("calisma_id"))].append(x)

    sft_hazir, dpo_hazir = mevcut_idler(y["sft"]), mevcut_idler(y["dpo_adaylari"])
    sayac: Counter = Counter()
    for d in diyaloglar:
        for o in sft_ornekleri(d, args.tam_diyalog):
            if o["id"] not in sft_hazir:
                jsonl_ekle(y["sft"], o)
                sayac["sft"] += 1
                sayac["kategori:" + o["kategori"]] += 1
        for o in dpo_adaylari(d, denemeler[(d["id"], d.get("calisma_id"))]):
            if o["id"] not in dpo_hazir:
                jsonl_ekle(y["dpo_adaylari"], o)
                sayac["dpo"] += 1
                sayac.update("red:" + r for r in o["red_nedeni"])
    print(f"Diyalog: {len(diyaloglar)} (bitiş ∈ {sorted(izinli)})")
    for k, c in sorted(sayac.items()):
        print(f"  {k:<32} {c}")


if __name__ == "__main__":
    main()
