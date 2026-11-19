"""GSM8K socratic biçimini ayrıştırma ve EN/TR satır eşleme."""
from __future__ import annotations

from .sayilar import etiket_sonuclari, icinde, sayi_ayristir, tokenlar


def socratic_ayristir(answer: str, dil: str = "en") -> tuple[list[dict], float | None]:
    """`answer` alanını adımlara ayırır.

    Her `####` öncesi satır bir adım: `**` öncesi alt soru, sonrası açıklama.
    Adım değeri: satırdaki son `<<ifade=sonuç>>` etiketinin sonucu; etiket yoksa None.
    Dönüş: (adimlar, son_cevap). Son cevap ayrıştırılamazsa None.
    """
    govde, ayrac, son = (answer or "").rpartition("####")
    if not ayrac:
        govde, son = answer or "", ""
    adimlar = []
    for satir in (s.strip() for s in govde.strip().split("\n")):
        if not satir:
            continue
        if "**" in satir:
            alt, _, aciklama = satir.partition("**")
        else:
            # VARSAYIM: '**' içermeyen satırın alt sorusu boş, tamamı açıklama sayılır.
            alt, aciklama = "", satir
        degerler = etiket_sonuclari(satir, dil)
        adimlar.append({
            "no": len(adimlar) + 1,
            "alt_soru": alt.strip(),
            "aciklama": aciklama.strip(),
            "deger": degerler[-1] if degerler else None,
        })
    return adimlar, sayi_ayristir(son.strip(), dil)


def son_cevap_ham(answer: str) -> str:
    return (answer or "").rpartition("####")[2].strip()


def kayma_bul(en_satirlar: list[dict], tr_satirlar: list[dict], ornek: int = 300,
              adaylar=(0, 1, -1, 2, -2)) -> tuple[int, float]:
    """TR[i] ↔ EN[i+kayma] eşlemesi için en iyi kaymayı son cevap uyumuna bakarak bulur."""
    def uyum(k: int) -> float:
        n = toplam = 0
        for i in range(min(ornek, len(tr_satirlar))):
            j = i + k
            if 0 <= j < len(en_satirlar):
                toplam += 1
                n += son_cevaplar_uyumlu(en_satirlar[j]["answer"], tr_satirlar[i]["answer"])
        return n / toplam if toplam else 0.0
    sonuclar = [(uyum(k), k) for k in adaylar]
    oran, kayma = max(sonuclar)
    return kayma, oran


def son_cevaplar_uyumlu(en_answer: str, tr_answer: str) -> bool:
    en = sayi_ayristir(son_cevap_ham(en_answer), "en")
    if en is None:
        return False
    tr_toks = tokenlar(son_cevap_ham(tr_answer), "tr")
    return any(icinde(en, t.adaylar) for t in tr_toks)
