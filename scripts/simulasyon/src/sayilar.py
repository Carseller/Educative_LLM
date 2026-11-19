"""Metinden sayı çıkarma ve toleranslı karşılaştırma (İngilizce / Türkçe).

Kurallar
- İngilizce: `1,200` binlik, `0.5` ondalık. `$`/`%` gibi işaretler zaten rakam olmadığı için atılır.
- Türkçe : `1.200` binlik, `0,5` ondalık, `1 200` (boşluklu binlik) olabilir.
- Belirsiz biçimler (ör. Türkçe metinde `1.250`, İngilizce alışkanlıkla yazılmış `0.5`) için her
  belirteç birden çok **aday** değer taşır; ilki birincil yorumdur. Karşılaştırma fonksiyonları
  istenirse tüm adaylara bakar.
- Kesir `3/4`: kesir değeri (0.75) **ve** iki ayrı tam sayı (3, 4) olarak döner.
- Yazıyla sayılar ("on iki", "yarım", "twelve") kapsam dışıdır.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MUTLAK_TOL = 1e-6
GORELI_TOL = 1e-4


def esit(a, b) -> bool:
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    fark = abs(a - b)
    return fark < MUTLAK_TOL or fark <= GORELI_TOL * max(abs(a), abs(b))


def icinde(x, liste) -> bool:
    return x is not None and any(esit(x, y) for y in liste)


def benzersiz(liste) -> list[float]:
    cikti: list[float] = []
    for x in liste:
        if not icinde(x, cikti):
            cikti.append(float(x))
    return cikti


@dataclass
class SayiToken:
    ham: str
    adaylar: list[float]
    bas: int = 0
    son: int = 0
    tur: str = "sayi"          # sayi | kesir | kesir_parca | birlesik
    alt: list[float] = field(default_factory=list)  # birleşik (boşluklu binlik) için parçalar

    @property
    def birincil(self) -> float:
        return self.adaylar[0]


# eksi işareti yalnızca başta / boşluk, '(' '=' ':' sonrasında; "48-24" bir çıkarma, -24 değil
_SAYI_RE = re.compile(
    r"(?P<eksi>(?<![^\s(=:\[])[-−])?"
    r"(?P<a>\d+(?:[.,]\d+)*|(?<![\w.,])\.\d+)"
    r"(?:\s*/\s*(?P<b>\d+(?:[.,]\d+)*))?"
)
_SIRA_RE = re.compile(r"\.\s*(adım|soru|kısım|kisim|basamak|aşama|asama|madde|sınıf|sinif|satır|satir|parça|parca)",
                      re.I)


def _int_or_float(s: str) -> float:
    return float(s)


def _yorumla_en(c: str) -> list[list[float]] | None:
    if re.fullmatch(r"\d+", c):
        return [[float(c)]]
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", c):
        return [[float(c.replace(",", ""))]]
    if re.fullmatch(r"\d+\.\d+", c):
        return [[float(c)]]
    return None


def _yorumla_tr(c: str) -> list[list[float]] | None:
    if re.fullmatch(r"\d+", c):
        return [[float(c)]]
    # 1.200 / 1.200.000 / 1.200,50 (TR binlik)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", c):
        tr = float(c.replace(".", "").replace(",", "."))
        if c.count(".") == 1 and "," not in c:
            return [[tr, float(c)]]          # tek nokta + 3 hane: İngilizce ondalık da olabilir
        return [[tr]]
    # 0,5 (TR ondalık); virgülden sonra tam 3 hane ise İngilizce binlik de olabilir
    if re.fullmatch(r"\d+,\d+", c):
        tr = float(c.replace(",", "."))
        sag = c.split(",")[1]
        if len(sag) == 3 and len(c.split(",")[0]) <= 3:
            return [[tr, float(c.replace(",", ""))]]
        return [[tr]]
    # 0.5 (çeviride korunmuş İngilizce ondalık)
    if re.fullmatch(r"\d+\.\d+", c):
        return [[float(c)]]
    # 1,200,000 veya 1,200.5 (çeviride korunmuş İngilizce binlik)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", c):
        return [[float(c.replace(",", ""))]]
    return None


def _yorumla(c: str, dil: str) -> list[list[float]]:
    """Ayraçlı çekirdeği aday listelerine çevirir. Geçersiz biçim ("3,4,5") parçalara bölünür."""
    if c.startswith("."):  # ".5" → 0.5 (İngilizce kısa ondalık)
        return [[float("0" + c)]]
    if dil == "en":
        r = _yorumla_en(c)
    elif dil == "tr":
        r = _yorumla_tr(c)
    else:  # auto: İngilizce birincil, Türkçe yorum aday olarak eklenir
        en, tr = _yorumla_en(c), _yorumla_tr(c)
        if en and tr:
            r = [benzersiz(en[0] + tr[0])]
        else:
            r = en or tr
    if r is None:
        return [[float(p)] for p in re.split(r"[.,]", c) if p]
    return r


def tokenlar(metin: str, dil: str = "tr", sira_atla: bool = False) -> list[SayiToken]:
    """Metindeki sayı belirteçleri. dil: 'en' | 'tr' | 'auto'.

    sira_atla=True ise Türkçe sıra sayıları ("2. adım") atlanır.
    """
    if not metin:
        return []
    cikti: list[SayiToken] = []
    for m in _SAYI_RE.finditer(metin):
        if sira_atla and m.group("b") is None and _SIRA_RE.match(metin, m.end("a")):
            continue
        isaret = -1.0 if m.group("eksi") else 1.0
        a_gruplari = _yorumla(m.group("a"), dil)
        if m.group("b") is None:
            for grup in a_gruplari:
                cikti.append(SayiToken(m.group(0), [isaret * x for x in grup], m.start(), m.end()))
                isaret = 1.0
            continue
        b_gruplari = _yorumla(m.group("b"), dil)
        a, b = a_gruplari[-1], b_gruplari[0]
        kesir = [isaret * x / y for x in a for y in b if y != 0]
        if kesir:
            cikti.append(SayiToken(m.group(0), benzersiz(kesir), m.start(), m.end(), tur="kesir"))
        for grup in a_gruplari:
            cikti.append(SayiToken(m.group("a"), [isaret * x for x in grup], m.start(), m.end(), tur="kesir_parca"))
            isaret = 1.0
        for grup in b_gruplari:
            cikti.append(SayiToken(m.group("b"), grup, m.start(), m.end(), tur="kesir_parca"))
    if dil == "tr":
        cikti = _bosluklu_binlik_birlestir(metin, cikti)
    return cikti


def _bosluklu_binlik_birlestir(metin: str, toks: list[SayiToken]) -> list[SayiToken]:
    """'1 200' → 1200 (birincil); parçalar (1, 200) aday olarak tutulur."""
    sonuc: list[SayiToken] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.tur == "sayi" and re.fullmatch(r"\d{1,3}", t.ham):
            j = i
            parcalar = [t]
            while (j + 1 < len(toks) and toks[j + 1].tur == "sayi" and re.fullmatch(r"\d{3}", toks[j + 1].ham)
                   and re.fullmatch(r"[   ]", metin[toks[j].son:toks[j + 1].bas])):
                j += 1
                parcalar.append(toks[j])
            if len(parcalar) > 1:
                birlesik = float("".join(p.ham for p in parcalar))
                altlar = [p.birincil for p in parcalar]
                sonuc.append(SayiToken(metin[t.bas:parcalar[-1].son], benzersiz([birlesik] + altlar),
                                       t.bas, parcalar[-1].son, tur="birlesik", alt=altlar))
                i = j + 1
                continue
        sonuc.append(t)
        i += 1
    return sonuc


def sayilari_cikar(metin: str, dil: str = "tr", genis: bool = True, sira_atla: bool = False) -> list[float]:
    """Metindeki sayılar (sırayı koruyarak, tekrarsız).

    genis=True: her belirtecin tüm aday yorumları; False: yalnızca birincil yorumlar.
    Kesirler her iki durumda da kesir değeri + parçalar olarak döner.
    """
    degerler: list[float] = []
    for t in tokenlar(metin, dil, sira_atla=sira_atla):
        degerler.extend(t.adaylar if genis else [t.birincil])
    return benzersiz(degerler)


def sayi_ayristir(s: str, dil: str = "en") -> float | None:
    """Tek bir sayı içeren metni (ör. '#### 1,200' sonrası) ayrıştırır; tam bir sayı yoksa None."""
    toks = [t for t in tokenlar(s or "", dil) if t.tur in ("sayi", "kesir", "birlesik")]
    if len(toks) != 1:
        return None
    return toks[0].birincil


def kume_esit(a: list[SayiToken], b: list[SayiToken]) -> bool:
    """İki metnin sayı kümeleri uyumlu mu: her belirtecin bir adayı diğer taraftaki adaylardan biriyle eşleşmeli."""
    a_tum = benzersiz([x for t in a for x in t.adaylar])
    b_tum = benzersiz([x for t in b for x in t.adaylar])
    return all(any(icinde(x, b_tum) for x in t.adaylar) for t in a) and \
        all(any(icinde(x, a_tum) for x in t.adaylar) for t in b)


_ETIKET_RE = re.compile(r"<<([^<>]*)>>")


def etiket_sonuclari(satir: str, dil: str = "en") -> list[float]:
    """`<<ifade=sonuç>>` etiketlerinin sonuçları (sırayla). Ayrıştırılamayan sonuç atlanır."""
    sonuclar = []
    for ic in _ETIKET_RE.findall(satir or ""):
        if "=" not in ic:
            continue
        sonuc = ic.rpartition("=")[2].strip()
        x = sayi_ayristir(sonuc, dil)
        if x is not None:
            sonuclar.append(x)
    return sonuclar


def bicimle(x, dil: str = "tr") -> str:
    """Sayıyı yazıya döker: tam sayılar ondalıksız; Türkçede ondalık ayırıcı virgül."""
    if x is None:
        return ""
    x = float(x)
    if abs(x - round(x)) < MUTLAK_TOL:
        return str(int(round(x)))
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if dil == "tr" else s
