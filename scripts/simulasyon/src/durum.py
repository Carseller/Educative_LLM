"""Öğrencinin diyalog boyunca değişen durumu (OgrenciDurumu).

`guncelle(js)` yalnızca hakemden geçmiş öğrenci JSON'u ile çağrılır.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .sayilar import esit, icinde, sayilari_cikar


@dataclass
class AdimDurumu:
    no: int
    durum: str                     # biliyor | hatali | kilitli
    deger: float | None
    alt_soru_tr: str = ""
    hata_tipi: str | None = None
    tamamlandi: bool = False
    hata_duzeltildi: bool = False
    kilit_acildi: bool = False
    yanlis_deneme: int = 0         # bu adımda verilen yanlış değer sayısı (açılış dahil)
    dogrulanamadi: bool = False    # değeri null olduğu için doğrulanmadan tamamlandı


@dataclass
class OgrenciDurumu:
    adimlar: list[AdimDurumu]
    son_cevap: float
    israr_taktikleri: list[str] = field(default_factory=list)
    israr_kullanilan: list[str] = field(default_factory=list)
    son_cevap_verildi: bool = False
    tamamlandi: bool = False
    ogrenci_kapatti: bool = False
    olaylar: list[dict] = field(default_factory=list)   # loglanan, doğrulanamayan geçişler

    # ------------------------------------------------------------ kurulum
    @classmethod
    def baslat(cls, senaryo: dict) -> "OgrenciDurumu":
        d = cls(
            adimlar=[AdimDurumu(no=a["no"], durum=a["durum"], deger=a["deger"], alt_soru_tr=a.get("alt_soru_tr", ""),
                                hata_tipi=a.get("hata_tipi")) for a in senaryo["adimlar"]],
            son_cevap=senaryo["son_cevap"],
            israr_taktikleri=list(senaryo["persona"].get("israr_taktikleri", [])),
        )
        d._acilisi_isle(senaryo)
        return d

    def _acilisi_isle(self, senaryo: dict) -> None:
        """Açılış mesajında gösterilen çalışmayı duruma yansıtır.

        VARSAYIM: yanlis_denemeli/kontrol_isteyen açılışlarında, baştan itibaren `biliyor` olup doğru
        değeri mesajda geçen adımlar tamamlanmış sayılır (ilk eksik adımda durulur). Hatalı adımdaki
        yanlış değer bir yanlış deneme sayılır. kontrol_isteyen + hepsi_biliyor'da doğru son cevap
        verildiyse bütün adımlar tamamlanır.
        """
        p = senaryo["persona"]
        mesaj = senaryo.get("acilis_mesaji") or ""
        if p["acilis"] not in ("yanlis_denemeli", "kontrol_isteyen") or not mesaj:
            return
        sayilar = sayilari_cikar(mesaj, "tr")
        verilen = senaryo.get("acilis_verilen_deger")
        if p["acilis"] == "kontrol_isteyen" and senaryo["bilgi_sablonu"] == "hepsi_biliyor" and esit(verilen, self.son_cevap):
            for a in self.adimlar:
                a.tamamlandi = True
            self.son_cevap_verildi = True
            self._olay("acilis_dogru_son_cevap")
            return
        for a in self.adimlar:
            if a.durum != "biliyor" or a.deger is None or not icinde(a.deger, sayilar):
                break
            a.tamamlandi = True
            self._olay("acilista_tamamlandi", adim=a.no)
        for a in self.adimlar:
            if a.durum == "hatali":
                a.yanlis_deneme += 1
                self._olay("acilista_hatali_deneme", adim=a.no)
                break

    # ------------------------------------------------------------ özellikler
    @property
    def n(self) -> int:
        return len(self.adimlar)

    @property
    def aktif_adim(self) -> int:
        """İlk tamamlanmamış adımın numarası; hepsi tamamsa n+1."""
        for a in self.adimlar:
            if not a.tamamlandi:
                return a.no
        return self.n + 1

    def adim(self, no: int | None) -> AdimDurumu | None:
        if no is None or not (1 <= no <= self.n):
            return None
        return self.adimlar[no - 1]

    @property
    def israr_kalan(self) -> int:
        return len(self.israr_taktikleri) - len(self.israr_kullanilan)

    @property
    def siradaki_taktik(self) -> str | None:
        return self.israr_taktikleri[len(self.israr_kullanilan)] if self.israr_kalan > 0 else None

    @property
    def kapanis_bekliyor(self) -> bool:
        """Öğretmenin bir kapanış/onay turu yazması gerekiyor mu?"""
        return (self.son_cevap_verildi or self.ogrenci_kapatti) and not self.tamamlandi

    def dogru_mu(self, no: int, deger) -> bool | None:
        """Verilen değer bu adım için doğru mu? Adım değeri bilinmiyorsa None.

        Son adımda son cevap da kabul edilir (son adım değeri son cevaptan farklı olabilir).
        """
        a = self.adim(no)
        if a is None or deger is None:
            return None
        if no == self.n and esit(deger, self.son_cevap):
            return True
        if a.deger is None:
            return None
        return esit(deger, a.deger)

    # ------------------------------------------------------------ güncelleme
    def guncelle(self, js: dict) -> None:
        if js.get("israr_taktigi"):
            self.israr_kullanilan.append(js["israr_taktigi"])
        if js.get("kapatmak_istiyor"):
            self.ogrenci_kapatti = True

        k = js.get("denenen_adim")
        a = self.adim(k)
        if js.get("kilit_acildi"):
            # VARSAYIM: kilit, denenen adım kilitliyse onda; değilse aktif adımda açılır.
            hedef = a if (a and a.durum == "kilitli") else self.adim(self.aktif_adim)
            if hedef and hedef.durum == "kilitli" and not hedef.kilit_acildi:
                hedef.kilit_acildi = True
                # Python ipucunun yeterliliğini doğrulayamaz; yalnızca loglanır.
                self._olay("kilit_acildi_ogrenci_beyani", adim=hedef.no)

        tahmin = js.get("tahmin_listesi") or []
        v = js.get("verilen_deger")
        if a is None or len(tahmin) >= 2:
            return  # VARSAYIM: çoklu tahmin bir adımı tamamlamaz
        if a.deger is None and k != self.n:
            if v is not None or js.get("mesaj"):
                # VARSAYIM: değeri bilinmeyen adım, öğrenci onu denediğini bildirince tamamlanır.
                a.tamamlandi = True
                a.dogrulanamadi = True
                self._olay("degersiz_adim_tamamlandi", adim=a.no)
        elif v is not None:
            dogru = self.dogru_mu(k, v)
            if dogru:
                a.tamamlandi = True
                if a.durum == "hatali" and not a.hata_duzeltildi:
                    a.hata_duzeltildi = True
                    self._olay("hata_duzeltildi", adim=a.no)
                if esit(v, self.son_cevap):
                    self._ozet_adimlari_kapat(k)
            elif dogru is False:
                a.yanlis_deneme += 1
        if self.adimlar[-1].tamamlandi:
            self.son_cevap_verildi = True

    def _ozet_adimlari_kapat(self, k: int) -> None:
        """VARSAYIM: son cevaba eşit değer verildiyse, ardından gelen değersiz ya da son cevaba eşit
        ("Therefore, X kept 36 apples." gibi özet) adımlar da tamamlanmış sayılır."""
        sonrakiler = self.adimlar[k:]
        if all(a.deger is None or esit(a.deger, self.son_cevap) for a in sonrakiler):
            for a in sonrakiler:
                if not a.tamamlandi:
                    a.tamamlandi = True
                    a.dogrulanamadi = a.deger is None
                    self._olay("ozet_adim_tamamlandi", adim=a.no)

    def ogretmen_turu_eklendi(self) -> None:
        """Öğretmen turu kabul edilip eklendikten sonra çağrılır."""
        if self.son_cevap_verildi or self.ogrenci_kapatti:
            self.tamamlandi = True

    def _olay(self, tur: str, **kw) -> None:
        self.olaylar.append({"olay": tur, **kw})

    def ozet(self) -> dict:
        return {
            "aktif_adim": self.aktif_adim,
            "adimlar": [{k: v for k, v in asdict(a).items() if k not in ("alt_soru_tr",)} for a in self.adimlar],
            "israr_kalan": self.israr_kalan,
            "son_cevap_verildi": self.son_cevap_verildi,
            "tamamlandi": self.tamamlandi,
            "ogrenci_kapatti": self.ogrenci_kapatti,
        }
