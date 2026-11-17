"""SocraTeach_multi.json keşif analizi.

Kullanım:
    python socrateach_analiz.py SocraTeach_multi.json

Alan adları README'den alındı ama dosyadaki gerçek yapı farklı olabilir.
Betik önce ilk kaydın yapısını yazdırır; istatistik kısmı alanları
esnek biçimde arar. Bir şey eşleşmezse çıktıdaki yapı dökümüne bakıp
ALAN_* sabitlerini güncelleyin.
"""
import collections
import json
import re
import statistics
import sys

ALAN_CEVAP = ["answer", "Answer"]
ALAN_DIYALOG = ["Teaching Dialogues", "dialogues", "Teaching Dialogue"]
OGRETMEN_ROLLERI = {"system", "teacher", "assistant"}
OGRENCI_ROLLERI = {"user", "student"}

SAYI = re.compile(r"-?\d+(?:[.,]\d+)?")


def kisalt(s, n=120):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def yapi(o, girinti=0, derinlik=5):
    """Nesnenin iskeletini (anahtarlar, tipler, kısa örnek değerler) yazdır."""
    bosluk = "  " * girinti
    if derinlik == 0:
        print(f"{bosluk}…")
        return
    if isinstance(o, dict):
        for k, v in list(o.items())[:12]:
            if isinstance(v, (dict, list)):
                print(f"{bosluk}{k!r}: {type(v).__name__}({len(v)})")
                yapi(v, girinti + 1, derinlik - 1)
            else:
                print(f"{bosluk}{k!r}: {kisalt(v)}")
        if len(o) > 12:
            print(f"{bosluk}… (+{len(o) - 12} anahtar)")
    elif isinstance(o, list):
        if o:
            print(f"{bosluk}[0]:")
            yapi(o[0], girinti + 1, derinlik - 1)
    else:
        print(f"{bosluk}{kisalt(o)}")


def al(d, adaylar):
    if not isinstance(d, dict):
        return None
    for a in adaylar:
        if a in d:
            return d[a]
    return None


def anahtar_bul(o, hedef, sonuc):
    """Verilen anahtarın tüm değerlerini özyinelemeli topla."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == hedef and not isinstance(v, (dict, list)):
                sonuc.append(v)
            anahtar_bul(v, hedef, sonuc)
    elif isinstance(o, list):
        for x in o:
            anahtar_bul(x, hedef, sonuc)
    return sonuc


def diyaloglari_cikar(kayit):
    """Kayıttaki diyalogları liste olarak döndür (yapı bilinmediği için esnek)."""
    d = al(kayit, ALAN_DIYALOG)
    if d is None:
        return []
    if isinstance(d, dict):
        return list(d.values())
    if isinstance(d, list):
        return d
    return []


def turlari_cikar(diyalog):
    """Diyalogdan (rol, metin) sırası çıkar. Desteklenen biçimler:
    - [{"role": "...", "content": "..."}]
    - [{"system": "...", "user": "..."}]  (her öğe bir tur çifti)
    - {"dialogue": [...], "user_type": ...}
    """
    if isinstance(diyalog, dict):
        for k in ("dialogue", "dialog", "turns", "messages", "conversation", "history"):
            if isinstance(diyalog.get(k), list):
                return turlari_cikar(diyalog[k])
        # Düz sözlük: rol anahtarları sırayla
        return [(k, v) for k, v in diyalog.items()
                if k in OGRETMEN_ROLLERI | OGRENCI_ROLLERI and isinstance(v, str)]
    turlar = []
    if isinstance(diyalog, list):
        for t in diyalog:
            if isinstance(t, dict) and "role" in t:
                turlar.append((t["role"], str(t.get("content", ""))))
            elif isinstance(t, dict):
                for k, v in t.items():
                    if k in OGRETMEN_ROLLERI | OGRENCI_ROLLERI and isinstance(v, str):
                        turlar.append((k, v))
            elif isinstance(t, (list, tuple)) and len(t) == 2:
                turlar.append(("pair_a", str(t[0])))
                turlar.append(("pair_b", str(t[1])))
    return turlar


def sayilar(metin):
    out = set()
    for m in SAYI.findall(metin):
        try:
            out.add(float(m.replace(",", ".")))
        except ValueError:
            pass
    return out


def cevap_sayisi(cevap):
    if cevap is None:
        return None
    bulunan = SAYI.findall(str(cevap))
    if not bulunan:
        return None
    try:
        return float(bulunan[-1].replace(",", "."))
    except ValueError:
        return None


def sizinti(turlar, cevap):
    """Öğretmen son cevabı öğrenciden önce söyledi mi?
    Döner: True (sızıntı), False (öğrenci önce söyledi), None (hiç geçmiyor)."""
    for rol, metin in turlar:
        if cevap in sayilar(metin):
            if rol in OGRETMEN_ROLLERI:
                return True
            if rol in OGRENCI_ROLLERI:
                return False
    return None


def main(yol):
    with open(yol, encoding="utf-8") as f:
        veri = json.load(f)

    if isinstance(veri, dict):
        anahtarlar = list(veri.keys())
        kayitlar = list(veri.values())
    else:
        anahtarlar = list(range(len(veri)))
        kayitlar = veri

    print("=" * 70)
    print("1) GENEL YAPI")
    print("=" * 70)
    print(f"Üst düzey tip: {type(veri).__name__}, kayıt sayısı: {len(kayitlar)}")
    print("İlk 5 anahtar:")
    for k in anahtarlar[:5]:
        print("  ", kisalt(k, 100))
    print("\nİlk kaydın yapısı:")
    yapi(kayitlar[0])

    print("\n" + "=" * 70)
    print("2) SAYILAR")
    print("=" * 70)
    diy_sayisi, tur_sayisi = [], []
    for k in kayitlar:
        dl = diyaloglari_cikar(k)
        diy_sayisi.append(len(dl))
        for d in dl:
            tur_sayisi.append(len(turlari_cikar(d)))
    print(f"Benzersiz soru: {len(kayitlar)}")
    print(f"Toplam diyalog: {sum(diy_sayisi)}")
    if diy_sayisi and sum(diy_sayisi):
        print(f"Soru başına diyalog: min {min(diy_sayisi)}, medyan "
              f"{statistics.median(diy_sayisi)}, maks {max(diy_sayisi)}")
    if tur_sayisi and sum(tur_sayisi):
        print(f"Diyalog başına mesaj: min {min(tur_sayisi)}, medyan "
              f"{statistics.median(tur_sayisi)}, maks {max(tur_sayisi)}")
    else:
        print("UYARI: Diyalog turları çıkarılamadı. Yapı dökümüne bakıp "
              "turlari_cikar() fonksiyonunu uyarlayın.")

    roller = collections.Counter()
    for k in kayitlar[:200]:
        for d in diyaloglari_cikar(k):
            for rol, _ in turlari_cikar(d):
                roller[rol] += 1
    print(f"Görülen roller (ilk 200 soru): {dict(roller)}")

    gsm = sum(1 for a in anahtarlar if "GSM8K" in str(a))
    print(f"Anahtarında 'GSM8K' geçen kayıt: {gsm}")

    print("\n" + "=" * 70)
    print("3) user_type DAĞILIMI VE ÖRNEKLER")
    print("=" * 70)
    tipler = collections.Counter()
    ornek = {}
    for k in kayitlar:
        for d in diyaloglari_cikar(k):
            ut = anahtar_bul(d, "user_type", [])
            t = str(ut[0]) if ut else "(yok)"
            tipler[t] += 1
            if t not in ornek:
                ornek[t] = turlari_cikar(d)
    for t, n in tipler.most_common():
        print(f"  {t}: {n}")
    for t, turlar in ornek.items():
        print(f"\n--- Örnek: {kisalt(t, 80)} ---")
        for rol, metin in turlar[:6]:
            print(f"  [{rol}] {kisalt(metin, 200)}")

    print("\n" + "=" * 70)
    print("4) SIZINTI ÖLÇÜMÜ (öğretmen son cevabı öğrenciden önce söylüyor mu)")
    print("=" * 70)
    sonuc = collections.Counter()
    tip_sizinti = collections.defaultdict(collections.Counter)
    for k in kayitlar:
        c = cevap_sayisi(al(k, ALAN_CEVAP))
        if c is None:
            sonuc["cevap_okunamadi"] += 1
            continue
        for d in diyaloglari_cikar(k):
            ut = anahtar_bul(d, "user_type", [])
            t = str(ut[0]) if ut else "(yok)"
            s = sizinti(turlari_cikar(d), c)
            etiket = {True: "sizinti", False: "ogrenci_once", None: "gecmiyor"}[s]
            sonuc[etiket] += 1
            tip_sizinti[t][etiket] += 1
    toplam = sum(v for k, v in sonuc.items() if k != "cevap_okunamadi")
    for k, v in sonuc.items():
        oran = f" (%{100 * v / toplam:.1f})" if toplam and k != "cevap_okunamadi" else ""
        print(f"  {k}: {v}{oran}")
    print("\nTipe göre:")
    for t, c in tip_sizinti.items():
        n = sum(c.values())
        print(f"  {kisalt(t, 60)}: sızıntı %{100 * c['sizinti'] / n:.1f} ({n} diyalog)")
    print("\nNot: Bu kaba bir ölçüm. Problem metninde son cevapla aynı sayı "
          "geçiyorsa yanlış alarm verir; 'sızıntı' örneklerinden birkaçını elle okuyun.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
