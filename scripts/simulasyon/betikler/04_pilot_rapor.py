#!/usr/bin/env python3
"""Pilot raporu: ekrana ve loglar/pilot_rapor.md dosyasına yazar.

Girdi: veri/senaryolar_acilisli.jsonl, veri/atilan_senaryolar.jsonl, veri/ham_diyaloglar.jsonl,
       veri/atilan_diyaloglar.jsonl, loglar/denemeler.jsonl
"""
from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ortak import config_yukle, jsonl_oku, rng  # noqa: E402


def _yuzde(a: int, b: int) -> str:
    return f"%{100 * a / b:.1f}" if b else "-"


def _tablo(basliklar: list[str], satirlar: list[list]) -> list[str]:
    cikti = ["| " + " | ".join(basliklar) + " |", "|" + "---|" * len(basliklar)]
    cikti += ["| " + " | ".join(str(x) for x in s) + " |" for s in satirlar]
    return cikti + [""]


def _zaman(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def diyalog_metni(d: dict) -> list[str]:
    s = d["senaryo"]
    out = [f"#### {d['id']} — bitiş: {d['bitis']}",
           f"şablon={s['bilgi_sablonu']}, açılış={s['persona']['acilis']}, davranış={s['persona']['davranis']}, "
           f"üslup={s['uslup']}, son cevap={s['son_cevap']}", "", "```"]
    for m in d["mesajlar"]:
        if m["rol"] == "ogrenci":
            out.append(f"ÖĞRENCİ: {m['icerik']}")
        else:
            iz = (m.get("iz") or "").replace("\n", " ")
            out.append(f"  [iz, {len(iz.split())} kelime] {iz[:400]}{'…' if len(iz) > 400 else ''}")
            out.append(f"ÖĞRETMEN (deneme {m.get('deneme_sayisi')}): {m['icerik']}")
    out += ["```", ""]
    return out


def rapor(cfg: dict, ornek_sayisi: int = 3) -> str:
    y = cfg["_yollar"]
    acilisli = jsonl_oku(y["senaryolar_acilisli"])
    atilan_sen = jsonl_oku(y["atilan_senaryolar"])
    ham = jsonl_oku(y["ham_diyaloglar"])
    atilan = jsonl_oku(y["atilan_diyaloglar"])
    denemeler = jsonl_oku(y["denemeler"])
    L: list[str] = ["# Pilot raporu", ""]

    # 1. Senaryo / diyalog durumu ------------------------------------------------
    n_d = len(ham) + len(atilan)
    L += ["## 1. Senaryo ve diyalog durumu", ""]
    L += _tablo(["kalem", "adet", "pay"], [
        ["açılışı üretilen senaryo", len(acilisli), ""],
        ["açılışı atılan senaryo", len(atilan_sen), _yuzde(len(atilan_sen), len(acilisli) + len(atilan_sen))],
        ["çalıştırılan diyalog", n_d, ""],
        ["kaydedilen diyalog", len(ham), _yuzde(len(ham), n_d)],
        ["atılan diyalog", len(atilan), _yuzde(len(atilan), n_d)],
    ])
    bitis = Counter(d["bitis"] for d in ham)
    neden = Counter(d["neden"] for d in atilan)
    L += ["Bitiş türü / atılma nedeni:", ""]
    L += _tablo(["sonuç", "adet", "pay (tüm diyaloglar)"],
                [[k, c, _yuzde(c, n_d)] for k, c in bitis.most_common()] +
                [[f"atıldı: {k}", c, _yuzde(c, n_d)] for k, c in neden.most_common()])

    # 2. Rol başına deneme kabul oranı ve sorun kodları --------------------------
    L += ["## 2. Denemeler", ""]
    satir = []
    sorun_sayac: dict[str, Counter] = defaultdict(Counter)
    uyari_sayac: dict[str, Counter] = defaultdict(Counter)
    for rol in ("ogretmen", "ogrenci"):
        dd = [d for d in denemeler if d["rol"] == rol]
        kabul = sum(d["kabul"] for d in dd)
        ilk = [d for d in dd if d["deneme"] == 0]
        satir.append([rol, len(dd), _yuzde(kabul, len(dd)), _yuzde(sum(d["kabul"] for d in ilk), len(ilk)),
                      sum(d.get("ag_hatasi", 0) for d in dd),
                      sum(1 for d in dd if d.get("finish_reason") == "length")])
        for d in dd:
            sorun_sayac[rol].update(d["sorunlar"])
            uyari_sayac[rol].update(d.get("uyarilar", []))
    L += _tablo(["rol", "deneme", "kabul oranı", "ilk deneme kabul", "ağ hatası", "finish=length"], satir)
    for rol in ("ogretmen", "ogrenci"):
        n = sum(1 for d in denemeler if d["rol"] == rol)
        L += [f"Sorun kodları — {rol}:", ""]
        L += _tablo(["kod", "adet", "denemelerin payı"], [[k, c, _yuzde(c, n)] for k, c in sorun_sayac[rol].most_common()])
        if uyari_sayac[rol]:
            L += [f"Uyarılar (reddetmeyen) — {rol}: " + ", ".join(f"{k}={c}" for k, c in uyari_sayac[rol].most_common()), ""]

    # 3. Tur istatistikleri ve kırılımlar ----------------------------------------
    L += ["## 3. Öğretmen turu ve kırılımlar", ""]
    turlar = [sum(1 for m in d["mesajlar"] if m["rol"] == "ogretmen") for d in ham]
    if turlar:
        L += [f"Kaydedilen diyaloglarda öğretmen turu: ortalama {statistics.mean(turlar):.2f}, "
              f"medyan {statistics.median(turlar)}, en çok {max(turlar)}", ""]
    for ad, anahtar in (("bilgi şablonu", lambda s: s["bilgi_sablonu"]),
                        ("açılış", lambda s: s["persona"]["acilis"]),
                        ("davranış", lambda s: s["persona"]["davranis"])):
        grup: dict[str, dict] = defaultdict(lambda: {"ham": [], "atilan": 0})
        for d in ham:
            grup[anahtar(d["senaryo"])]["ham"].append(d)
        for d in atilan:
            grup[anahtar({"bilgi_sablonu": d["bilgi_sablonu"], "persona": d["persona"]})]["atilan"] += 1
        satirlar = []
        for k, g in sorted(grup.items()):
            t = [sum(1 for m in d["mesajlar"] if m["rol"] == "ogretmen") for d in g["ham"]]
            b = Counter(d["bitis"] for d in g["ham"])
            top = len(g["ham"]) + g["atilan"]
            satirlar.append([k, top, _yuzde(g["atilan"], top), f"{statistics.mean(t):.2f}" if t else "-",
                             _yuzde(b["cozuldu"], top), _yuzde(b["ogrenci_kapatti"], top), _yuzde(b["tur_siniri"], top)])
        L += [f"Kırılım: {ad}", ""]
        L += _tablo([ad, "diyalog", "atılma", "ort. tur", "çözüldü", "öğr. kapattı", "tur sınırı"], satirlar)

    # 4. Sızıntı, iz dili, iz uzunluğu --------------------------------------------
    L += ["## 4. Sızıntı ve düşünme izi", ""]
    og = [d for d in denemeler if d["rol"] == "ogretmen"]
    sizinti = sum("sizinti" in d["sorunlar"] for d in og)
    L += [f"`sizinti` reddi: {sizinti}/{len(og)} öğretmen denemesi ({_yuzde(sizinti, len(og))})", ""]
    iz_dili = Counter(d.get("bilgi", {}).get("iz_dili", "?") for d in og)
    L += ["İz dili (tüm öğretmen denemeleri): " + ", ".join(f"{k}={c} ({_yuzde(c, len(og))})" for k, c in iz_dili.most_common()), ""]
    kel = [d["bilgi"].get("iz_kelime", 0) for d in og if d.get("bilgi")]
    kabul_kel = [d["bilgi"].get("iz_kelime", 0) for d in og if d.get("bilgi") and d["kabul"]]
    if kel:
        L += [f"İz uzunluğu (kelime): tüm denemeler ort. {statistics.mean(kel):.0f} / medyan {statistics.median(kel)}; "
              f"kabul edilenler ort. {statistics.mean(kabul_kel) if kabul_kel else 0:.0f}", ""]

    # 5. Hız -----------------------------------------------------------------------
    L += ["## 5. Hız", ""]
    calismalar: dict[str, list] = defaultdict(list)
    for d in ham:
        if d.get("baslangic") and d.get("bitis_zamani"):
            calismalar[d.get("calisma_id", "?")].append(d)
    satirlar = []
    for cid, dd in calismalar.items():
        bas = min(_zaman(d["baslangic"]) for d in dd)
        son = max(_zaman(d["bitis_zamani"]) for d in dd)
        saat = max((son - bas).total_seconds(), 1) / 3600
        satirlar.append([cid, len(dd), f"{saat * 60:.1f} dk", f"{len(dd) / saat:.0f}"])
    L += _tablo(["çalışma", "kaydedilen diyalog", "süre", "diyalog/saat"], satirlar)
    L += ["Not: süre çalışmadaki ilk diyalog başlangıcından son kayda kadardır (saniye çözünürlüğü).", ""]

    # 6. Örnek diyaloglar ----------------------------------------------------------
    L += ["## 6. Örnek diyaloglar", ""]
    r = rng(cfg["seed"], "pilot_rapor")
    for b in ("cozuldu", "ogrenci_kapatti", "tur_siniri"):
        aday = [d for d in ham if d["bitis"] == b]
        L += [f"### {b} ({len(aday)} diyalog)", ""]
        for d in r.sample(aday, min(ornek_sayisi, len(aday))):
            L += diyalog_metni(d)
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--ornek", type=int, default=3, help="Her bitiş türünden kaç örnek diyalog")
    args = ap.parse_args()
    cfg = config_yukle(args.config)
    metin = rapor(cfg, args.ornek)
    Path(cfg["_yollar"]["pilot_rapor"]).write_text(metin, encoding="utf-8")
    print(metin)
    print(f"\nYazıldı: {cfg['_yollar']['pilot_rapor']}")


if __name__ == "__main__":
    main()
