"""GSM8K İngilizce ve Türkçe satırlarını içerikle eşleştirir.

Türkçe sürümde bazı satırlar eksik olduğu için sıra numarasıyla eşleştirme
yapılamaz. Bu betik her İngilizce satıra karşılık gelen Türkçe satırı bulur.

Kullanım (repo kökünde, venv etkinken):
    python eslesme_olustur.py

Girdi:  kaynak_veri/gsm8k_{en,tr}_socratic_{train,test}.jsonl
Çıktı:  kaynak_veri/eslesme_{train,test}.jsonl
        Her satır: {"en": i, "tr": j | null, "durum": "tam" | "supheli" | "tr_eksik"}
"""
import json
import os
import re

KLASOR = "kaynak_veri"
ILERI_BAK = 5          # uyuşmazlıkta kaç satır ileriye bakılacak
ORTUSME_ESIK = 0.5     # soru sayılarının Jaccard benzerliği eşiği

SAYI_EN = re.compile(r"\d[\d,]*(?:\.\d+)?")
SAYI_TR = re.compile(r"\d[\d.]*(?:,\d+)?")


def en_sayi(s):
    try:
        return round(float(s.replace(",", "")), 6)
    except ValueError:
        return None


def tr_sayi(s):
    s = s.rstrip(".")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):      # 1.200 -> binlik
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return round(float(s), 6)
    except ValueError:
        return None


def sayilar(metin, dil):
    desen, cevir = (SAYI_EN, en_sayi) if dil == "en" else (SAYI_TR, tr_sayi)
    return {v for v in (cevir(m) for m in desen.findall(metin)) if v is not None}


def son_cevap(cevap, dil):
    if "####" not in cevap:
        return None
    s = sayilar(cevap.split("####")[-1], dil)
    return next(iter(s)) if len(s) == 1 else None


def oku(yol, dil):
    satirlar = []
    with open(yol, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            satirlar.append({
                "soru": r["question"],
                "sayilar": sayilar(r["question"], dil),
                "cevap": son_cevap(r["answer"], dil),
            })
    return satirlar


def benzerlik(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def uyuyor(e, t):
    return (e["cevap"] is not None and e["cevap"] == t["cevap"]
            and benzerlik(e["sayilar"], t["sayilar"]) >= ORTUSME_ESIK)


def eslestir(en, tr):
    sonuc, i, j = [], 0, 0
    while i < len(en):
        if j < len(tr) and uyuyor(en[i], tr[j]):
            sonuc.append({"en": i, "tr": j, "durum": "tam"}); i += 1; j += 1
            continue
        # İngilizce satır Türkçede eksik mi? (İngilizcede ileri bak)
        k_en = next((k for k in range(1, ILERI_BAK + 1)
                     if i + k < len(en) and j < len(tr) and uyuyor(en[i + k], tr[j])), None)
        # Türkçede fazladan satır mı var? (Türkçede ileri bak)
        k_tr = next((k for k in range(1, ILERI_BAK + 1)
                     if j + k < len(tr) and uyuyor(en[i], tr[j + k])), None)
        if k_en is not None and (k_tr is None or k_en <= k_tr):
            for m in range(k_en):
                sonuc.append({"en": i + m, "tr": None, "durum": "tr_eksik"})
            i += k_en
        elif k_tr is not None:
            j += k_tr      # Türkçedeki fazla satırlar atlanır (raporlanır)
            print(f"  UYARI: Türkçede eşi olmayan satır(lar): {list(range(j - k_tr, j))}")
        else:
            # Ne ileride ne geride eş yok: aynı konumdakini şüpheli olarak eşle
            sonuc.append({"en": i, "tr": j if j < len(tr) else None, "durum": "supheli"})
            i += 1; j += 1
    return sonuc


def main():
    for bolum in ("train", "test"):
        en = oku(os.path.join(KLASOR, f"gsm8k_en_socratic_{bolum}.jsonl"), "en")
        tr = oku(os.path.join(KLASOR, f"gsm8k_tr_socratic_{bolum}.jsonl"), "tr")
        print(f"\n=== {bolum}: İng {len(en)}, Tr {len(tr)} ===")
        sonuc = eslestir(en, tr)
        sayac = {}
        for s in sonuc:
            sayac[s["durum"]] = sayac.get(s["durum"], 0) + 1
        print("  Durumlar:", sayac)
        for s in sonuc:
            if s["durum"] == "tr_eksik":
                print(f"  Türkçede eksik -> İng satır {s['en']}: {en[s['en']]['soru'][:100]}")
        supheli = [s for s in sonuc if s["durum"] == "supheli"]
        for s in supheli[:5]:
            print(f"  Şüpheli örnek -> İng {s['en']}: {en[s['en']]['soru'][:80]}")
            if s["tr"] is not None:
                print(f"                   Tr  {s['tr']}: {tr[s['tr']]['soru'][:80]}")
        cikti = os.path.join(KLASOR, f"eslesme_{bolum}.jsonl")
        with open(cikti, "w", encoding="utf-8") as f:
            for s in sonuc:
                f.write(json.dumps(s) + "\n")
        print(f"  Yazıldı: {cikti}")


if __name__ == "__main__":
    main()
