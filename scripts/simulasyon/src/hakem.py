"""Deterministik hakem. Saf fonksiyonlar; LLM çağırmaz, dosya okumaz (ayarlar kurulumda verilir).

Her kontrol bir `SorunListesi` döndürür: bu bir `list`tir (boş = geçti). Ek olarak
`.uyarilar` (reddetmeyen, yalnızca loglanan kodlar) ve `.bilgi` (loglanacak ölçümler) taşır.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .ortak import tr_kucuk, yaml_oku
from .sayilar import esit, icinde, sayilari_cikar

# ---------------------------------------------------------------------------- dil sezgiseli
_TR_HARF = set("çğıöşüÇĞİÖŞÜ")
_TR_KELIME = set("""
ve bir bu şu o için ne kaç mı mi mu mü da de ile sen ben biz siz nasıl şimdi evet hayır değil var yok
olarak kadar daha çok gibi sonra önce toplam tane bence sanırım bilmiyorum cevap soru hangi neden niye
ama fakat çünkü eğer ise yani peki tamam olur oldu olan bunu şunu onu her hep hiç bile sadece yalnızca
ilk iki üç dört beş bul buldum yaptım yap yapalım bak düşün kere kez adım adımda sonuç sonucu doğru yanlış
mısın misin musun nedir ki diye gibi lütfen ya yoksa nereden nerede biraz bana sana ona onun senin benim
dolar lira saat dakika gün hafta ay yıl tl kg metre böl çarp topla çıkar işlem
""".split())
_EN_KELIME = set("""
the and is are of to you what how it in that this for with be was were have has had do does did not
your can will would should could let's lets we they he she his her their there here which who why when
answer question step first then so if but or because number total each per many much more less than
think need know right wrong yes no okay ok please just tell me give find calculate
""".split())


def _kelimeler(metin: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", tr_kucuk(metin or ""))


def dil_tespit(metin: str, en_ust: float = 0.2, en_alt_ingilizce: float = 0.8) -> str:
    """'tr' | 'en' | 'karisik' | 'belirsiz' (yeterli işaret yok)."""
    tr = en = 0
    for k in _kelimeler(metin):
        k_kok = k.split("'")[0]
        if any(c in _TR_HARF for c in k) or k_kok in _TR_KELIME:
            tr += 1
        elif k_kok in _EN_KELIME:
            en += 1
    if tr + en < 2:
        return "belirsiz"
    oran = en / (tr + en)
    if oran < en_ust:
        return "tr"
    if oran > en_alt_ingilizce:
        return "en"
    return "karisik"


def turkce_mi(metin: str, en_ust: float = 0.2, en_alt_ingilizce: float = 0.8) -> bool:
    return dil_tespit(metin, en_ust, en_alt_ingilizce) in ("tr", "belirsiz")


# ---------------------------------------------------------------------------- biçim
_BICIM_DESENLERI = [
    re.compile(r"\*\*"),                     # kalın
    re.compile(r"^\s*#{1,6}\s", re.M),       # başlık
    re.compile(r"^\s*[-*•]\s", re.M),        # madde işareti
    re.compile(r"^\s*\d+[.)]\s", re.M),      # numaralı liste
    re.compile(r"\$\$|\$[^$\d\s][^$]*\$"),  # LaTeX matematik ($x$, $$); "$5" para birimi değil
    re.compile(r"\\\(|\\\[|\\frac|\\cdot|\\times|\\text\{"),
]


def bicim_var_mi(metin: str) -> bool:
    """Markdown/LaTeX işaretleri. VARSAYIM: tek başına '$5' (para birimi) LaTeX sayılmaz."""
    return any(d.search(metin or "") for d in _BICIM_DESENLERI)


def kelime_sayisi(metin: str) -> int:
    return len(re.findall(r"\S+", metin or ""))


def benzerlik(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, tr_kucuk(a or ""), tr_kucuk(b or "")).ratio()


def _ifade_var(metin: str, ifadeler: list[str]) -> list[str]:
    """Listedeki eşleşen ifadeler. 're:' önekliler düzenli ifadedir."""
    kucuk = tr_kucuk(metin or "")
    bulunan = []
    for ifade in ifadeler:
        if ifade.startswith("re:"):
            if re.search(ifade[3:], metin or "", re.I) or re.search(ifade[3:], kucuk, re.I):
                bulunan.append(ifade)
        elif tr_kucuk(ifade) in kucuk:
            bulunan.append(ifade)
    return bulunan


# ---------------------------------------------------------------------------- adım ilgisi
_DURAK = set("""kaç kadar nedir için olan olarak toplam toplamda tane daha hangi nasıl sonra önce
şimdi yani peki şunu bunu onun buna şuna toplamı""".split())


def _kokler(metin: str) -> set[str]:
    """Türkçe ekler için kaba kök: ilk 5 harf; 4 harften kısa ve durak kelimeler atılır."""
    return {k[:5] for k in _kelimeler(metin) if len(k) >= 4 and k not in _DURAK}


def adim_ile_ilgili(metin: str, alt_soru: str) -> bool:
    """Metin, adımın alt sorusuyla anahtar kelime ya da sayı paylaşıyor mu? (sezgisel)"""
    if _kokler(metin) & _kokler(alt_soru):
        return True
    alt_sayilar = sayilari_cikar(alt_soru, "tr")
    return any(icinde(x, alt_sayilar) for x in sayilari_cikar(metin, "tr"))


# ---------------------------------------------------------------------------- sonuç tipi
class SorunListesi(list):
    def __init__(self, *a):
        super().__init__(*a)
        self.uyarilar: list[str] = []
        self.bilgi: dict = {}

    def ekle(self, kod: str) -> None:
        if kod not in self:
            self.append(kod)

    def uyar(self, kod: str) -> None:
        if kod not in self.uyarilar:
            self.uyarilar.append(kod)


# ---------------------------------------------------------------------------- hakem
OGRENCI_ALANLARI = ("denenen_adim", "verilen_deger", "kilit_acildi", "israr_taktigi",
                    "tahmin_listesi", "kapatmak_istiyor", "mesaj")


def _sayi_mi(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


@dataclass
class Hakem:
    maks_ogrenci_kelime: int = 60
    maks_ogretmen_kelime: int = 120
    maks_soru: int = 1
    tekrar_esik: float = 0.8
    ogrenci_tekrar_esik: float = 0.9
    dil_en_ust: float = 0.2
    dil_en_alt_ingilizce: float = 0.8
    israr_katalogu: list[str] = field(default_factory=list)
    ogretmen_yasakli: list[str] = field(default_factory=list)
    ogrenci_kaliplari: list[str] = field(default_factory=list)
    iz_desenleri: list[str] = field(default_factory=list)
    onay_kelimeleri: list[str] = field(default_factory=lambda: ["doğru", "evet", "aynen"])
    talep_ifadeleri: list[str] = field(default_factory=list)

    @classmethod
    def yukle(cls, cfg: dict) -> "Hakem":
        y = yaml_oku(Path(cfg["_yollar"]["istem"]) / cfg["istemler"]["yasakli_ifadeler"])
        return cls(
            maks_ogrenci_kelime=cfg["maks_ogrenci_kelime"], maks_ogretmen_kelime=cfg["maks_ogretmen_kelime"],
            maks_soru=cfg["maks_soru"], tekrar_esik=cfg["tekrar_esik"],
            ogrenci_tekrar_esik=cfg.get("ogrenci_tekrar_esik", 0.9),
            dil_en_ust=cfg.get("dil_en_orani_ust", 0.2), dil_en_alt_ingilizce=cfg.get("dil_en_orani_alt_ingilizce", 0.8),
            israr_katalogu=list(cfg["israr_taktikleri"]),
            ogretmen_yasakli=y.get("ogretmen_yasakli", []), ogrenci_kaliplari=y.get("ogrenci_ogretmen_kalibi", []),
            iz_desenleri=y.get("iz_talimat_desenleri", []), onay_kelimeleri=y.get("onay_kelimeleri", []),
            talep_ifadeleri=y.get("cevap_talep_ifadeleri", []),
        )

    def _turkce(self, metin: str) -> bool:
        return turkce_mi(metin, self.dil_en_ust, self.dil_en_alt_ingilizce)

    # ======================================================================== açılış
    def acilis_kontrol(self, js: dict | None, senaryo: dict) -> SorunListesi:
        s = SorunListesi()
        p = senaryo["persona"]
        acilis = p["acilis"]
        soru = senaryo["soru_tr"]
        if acilis in ("kopyala_yapistir", "cevabi_ne"):
            if not isinstance(js, dict) or not isinstance(js.get("on_ek"), str) or not isinstance(js.get("son_ek"), str):
                s.ekle("json_gecersiz")
                return s
            from .istemler import acilis_birlestir
            mesaj = acilis_birlestir(js, soru)
            ekler = f"{js['on_ek']} {js['son_ek']}".strip()
            if soru not in mesaj:
                s.ekle("soru_metni_yok")
            if sayilari_cikar(ekler, "tr"):
                s.ekle("ekte_sayi")
            if acilis == "cevabi_ne" and not _ifade_var(ekler, self.talep_ifadeleri):
                s.ekle("talep_yok")
            # VARSAYIM: kelime sınırı, dil ve biçim yalnızca eklere uygulanır (soru metni zaten uzun olabilir).
            denetlenen = ekler
        else:
            if not isinstance(js, dict) or not isinstance(js.get("mesaj"), str) or not js["mesaj"].strip() \
                    or not (js.get("verilen_deger") is None or _sayi_mi(js.get("verilen_deger"))):
                s.ekle("json_gecersiz")
                return s
            mesaj = js["mesaj"]
            v = js.get("verilen_deger")
            sayilar = sayilari_cikar(mesaj, "tr")
            son = senaryo["son_cevap"]
            if v is None:
                s.ekle("deger_yok")
            elif not icinde(v, sayilar):
                s.ekle("deger_tutarsiz")
            if acilis == "yanlis_denemeli":
                hatali = next((a for a in senaryo["adimlar"] if a["durum"] == "hatali"), None)
                if hatali is None:
                    s.ekle("senaryo_uyumsuz")
                else:
                    if v is not None and esit(v, hatali["deger"]):
                        s.ekle("deger_dogru")
                    izinli = list(senaryo["soru_sayilari"]) + [a["deger"] for a in senaryo["adimlar"]
                                                               if a["no"] < hatali["no"] and a["deger"] is not None]
                    if icinde(son, sayilar) and not icinde(son, izinli):
                        s.ekle("son_cevap_var")
                    yasak = [a["deger"] for a in senaryo["adimlar"] if a["no"] >= hatali["no"] and a["deger"] is not None]
                    if any(icinde(x, yasak) and not icinde(x, izinli) and not esit(x, son) for x in sayilar):
                        s.ekle("erken_sonuc")
            elif acilis == "kontrol_isteyen":
                if senaryo["bilgi_sablonu"] == "hepsi_biliyor":
                    if v is not None and not esit(v, son):
                        s.ekle("kontrol_deger_hatali")
                else:
                    if v is not None and esit(v, son):
                        s.ekle("kontrol_deger_hatali")
                    if icinde(son, sayilar) and not icinde(son, senaryo["soru_sayilari"]):
                        s.ekle("son_cevap_var")
            denetlenen = mesaj
        if kelime_sayisi(denetlenen) > self.maks_ogrenci_kelime:
            s.ekle("uzun")
        if denetlenen and not self._turkce(denetlenen):
            s.ekle("dil")
        if bicim_var_mi(denetlenen):
            s.ekle("bicim")
        if _ifade_var(denetlenen, self.ogrenci_kaliplari):
            s.ekle("ogretmen_kalibi")
        s.bilgi["mesaj"] = mesaj
        return s

    # ======================================================================== öğrenci
    def _ogrenci_json_hatasi(self, js, n: int) -> str | None:
        if not isinstance(js, dict):
            return "nesne_degil"
        eksik = [a for a in OGRENCI_ALANLARI if a not in js]
        if eksik:
            return f"eksik_alan:{','.join(eksik)}"
        if not isinstance(js["mesaj"], str) or not js["mesaj"].strip():
            return "mesaj_bos"
        k = js["denenen_adim"]
        if k is not None and (not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= n):
            return "denenen_adim_gecersiz"
        if js["verilen_deger"] is not None and not _sayi_mi(js["verilen_deger"]):
            return "verilen_deger_gecersiz"
        for b in ("kilit_acildi", "kapatmak_istiyor"):
            if not isinstance(js[b], bool):
                return f"{b}_bool_degil"
        t = js["israr_taktigi"]
        if t is not None and t not in self.israr_katalogu:
            return "israr_taktigi_bilinmiyor"
        tl = js["tahmin_listesi"]
        if tl is not None and (not isinstance(tl, list) or not all(_sayi_mi(x) for x in tl)):
            return "tahmin_listesi_gecersiz"
        return None

    def ogrenci_kontrol(self, js, senaryo: dict, mesajlar: list, durum) -> SorunListesi:
        s = SorunListesi()
        hata = self._ogrenci_json_hatasi(js, durum.n)
        if hata:
            s.ekle("json_gecersiz")
            s.bilgi["json_hatasi"] = hata
            return s
        mesaj = js["mesaj"]
        p = senaryo["persona"]
        k, v = js["denenen_adim"], js["verilen_deger"]
        tahmin = js["tahmin_listesi"] or []
        coklu_tahmin = len(tahmin) >= 2
        adim = durum.adim(k)

        # --- biçim
        if kelime_sayisi(mesaj) > self.maks_ogrenci_kelime:
            s.ekle("uzun")
        if not self._turkce(mesaj):
            s.ekle("dil")
        if bicim_var_mi(mesaj):
            s.ekle("bicim")
        if _ifade_var(mesaj, self.ogrenci_kaliplari):
            s.ekle("ogretmen_kalibi")
        onceki_ogrenci = [m.icerik for m in mesajlar if m.rol == "ogrenci"]
        if any(benzerlik(mesaj, o) > self.ogrenci_tekrar_esik for o in onceki_ogrenci):
            s.ekle("tekrar")

        # --- adım mantığı
        if k is not None and k > durum.aktif_adim:
            s.ekle("adim_sicramasi")
        mesaj_sayilari = sayilari_cikar(mesaj, "tr", sira_atla=True)  # "3. adım" bir değer değil
        if v is not None and not icinde(v, sayilari_cikar(mesaj, "tr")):
            s.ekle("deger_tutarsiz")

        dogru = durum.dogru_mu(k, v) if (adim and v is not None and not coklu_tahmin) else None
        if adim and dogru is False and (adim.durum == "biliyor" or (adim.durum == "hatali" and adim.hata_duzeltildi)):
            s.ekle("biliyor_yanlis")
        if adim and dogru and adim.durum == "hatali" and not adim.hata_duzeltildi:
            son_ogretmen = next((m.icerik for m in reversed(mesajlar) if m.rol == "ogretmen"), "")
            tum_ogretmen = [m.icerik for m in mesajlar if m.rol == "ogretmen"]
            # VARSAYIM: "emin" durum = hata hiç yapılmamış VE hiçbir öğretmen mesajı adımla ilgili değil → ret.
            # Hata önceden yapılmış ama son öğretmen mesajı adımla ilgisiz görünüyorsa → yalnızca uyarı.
            if not adim_ile_ilgili(son_ogretmen, adim.alt_soru_tr):
                if adim.yanlis_deneme == 0 and not any(adim_ile_ilgili(t, adim.alt_soru_tr) for t in tum_ogretmen):
                    s.ekle("hatali_erken_dogru")       # hata hiç yapılmadı ve öğretmen adıma hiç değinmedi
                else:
                    s.uyar("hatali_erken_dogru")       # sezgisel; emin olunamıyor → yalnızca uyarı
        # VARSAYIM: kilit aynı mesajda açılıp (kilit_acildi=true) doğru değer verilebilir.
        if adim and dogru and adim.durum == "kilitli" and not adim.kilit_acildi and not js["kilit_acildi"]:
            s.ekle("kilitli_erken")

        # --- erken sonuç
        izinli = list(senaryo["soru_sayilari"])
        for m in mesajlar:
            izinli.extend(sayilari_cikar(m.icerik, "tr"))
        yasak = [a.deger for a in durum.adimlar if a.deger is not None and not a.tamamlandi and a.no != k]
        if k != durum.n:
            yasak.append(durum.son_cevap)
        dogru_k = adim.deger if adim else None
        if adim and k == durum.n:
            dogru_k = durum.son_cevap if dogru_k is None else dogru_k
        erken = [x for x in mesaj_sayilari
                 if icinde(x, yasak) and not icinde(x, izinli) and not esit(x, dogru_k)
                 and not (k == durum.n and esit(x, durum.son_cevap))]
        if erken:
            istisna = p["davranis"] == "tahmin_avcisi" and coklu_tahmin and all(icinde(x, tahmin) for x in erken)
            if not istisna:
                s.ekle("erken_sonuc")
                s.bilgi["erken_degerler"] = erken

        # --- ısrar
        t = js["israr_taktigi"]
        if t is not None:
            if durum.israr_kalan <= 0:
                s.ekle("israr_hakki_yok")
            elif t != durum.siradaki_taktik:
                s.ekle("israr_sirasi")

        # --- kapatma
        if js["kapatmak_istiyor"]:
            bu_mesaj_bitiriyor = k == durum.n and dogru
            yorgun = p["davranis"] == "kaygili" or senaryo["uslup"].get("ton") == "yorgun"
            if not yorgun and not durum.son_cevap_verildi and not bu_mesaj_bitiriyor:
                s.ekle("erken_kapatma")
        return s

    # ======================================================================== öğretmen
    def yasak_degerler(self, senaryo: dict, mesajlar: list) -> list[float]:
        """Adım değerleri + son cevap − soru sayıları − öğrencinin şimdiye kadar söylediği sayılar."""
        ogrenci = []
        for m in mesajlar:
            if m.rol == "ogrenci":
                ogrenci.extend(sayilari_cikar(m.icerik, "tr"))
        izinli = list(senaryo["soru_sayilari"]) + ogrenci
        aday = [a["deger"] for a in senaryo["adimlar"] if a["deger"] is not None] + [senaryo["son_cevap"]]
        return [x for x in aday if not icinde(x, izinli)]

    def ogretmen_kontrol(self, cevap: str, iz: str, senaryo: dict, mesajlar: list, durum, tur: int) -> SorunListesi:
        s = SorunListesi()
        cevap, iz = cevap or "", iz or ""
        s.bilgi.update(iz_dili=dil_tespit(iz, self.dil_en_ust, self.dil_en_alt_ingilizce),
                       iz_kelime=kelime_sayisi(iz), iz_karakter=len(iz), cevap_kelime=kelime_sayisi(cevap))
        if not cevap.strip() or not iz.strip():
            s.ekle("bos")
            return s

        yasak = self.yasak_degerler(senaryo, mesajlar)
        # VARSAYIM: "2. adım" gibi sıra sayıları sızıntı sayılmaz. Kesirlerin parçaları ve belirsiz
        # biçimlerin tüm adayları sayılır (sıkı tarafta kalmak için).
        cevap_sayilari = sayilari_cikar(cevap, "tr", sira_atla=True)
        sizan = [x for x in cevap_sayilari if icinde(x, yasak)]
        if sizan:
            s.ekle("sizinti")
            s.bilgi["sizan_degerler"] = sizan
        if tur == 0 and not icinde(senaryo["son_cevap"], sayilari_cikar(iz, "auto")):
            s.ekle("iz_cevapsiz")
        atif = _ifade_var(iz, self.iz_desenleri)
        if atif:
            s.ekle("iz_talimat_atfi")
            s.bilgi["iz_talimat_atfi"] = atif
        if kelime_sayisi(cevap) > self.maks_ogretmen_kelime:
            s.ekle("uzun")
        if cevap.count("?") > self.maks_soru:
            s.ekle("cok_soru")
        if not self._turkce(cevap):
            s.ekle("dil")
        bulunan = _ifade_var(cevap, self.ogretmen_yasakli)
        if bulunan:
            s.ekle("yasakli_ifade")
            s.bilgi["yasakli_ifadeler"] = bulunan
        if bicim_var_mi(cevap):
            # VARSAYIM: talimatın öğretmen ret kodları arasında biçim yok; markdown/LaTeX yalnızca uyarı olarak loglanır.
            s.uyar("bicim")
        onceki = [m.icerik for m in mesajlar if m.rol == "ogretmen"]
        if any(benzerlik(cevap, o) > self.tekrar_esik for o in onceki):
            s.ekle("tekrar")

        son_ogrenci = next((m for m in reversed(mesajlar) if m.rol == "ogrenci"), None)
        tahmin = ((son_ogrenci.meta or {}).get("tahmin_listesi") or []) if son_ogrenci else []
        if len(tahmin) >= 2:
            k = (son_ogrenci.meta or {}).get("denenen_adim") or durum.aktif_adim
            dogrular = [x for x in tahmin if durum.dogru_mu(k, x)]
            onay = any(re.search(rf"(?<!\w){re.escape(tr_kucuk(o))}(?!\w)", tr_kucuk(cevap)) for o in self.onay_kelimeleri)
            if onay and any(icinde(x, cevap_sayilari) for x in dogrular):
                s.ekle("tahmin_onayi")
        return s

    # ======================================================================== bitiş
    @staticmethod
    def bitis_etiketi(durum) -> str:
        if durum.son_cevap_verildi:
            return "cozuldu"
        if durum.ogrenci_kapatti:
            return "ogrenci_kapatti"
        return "tur_siniri"
