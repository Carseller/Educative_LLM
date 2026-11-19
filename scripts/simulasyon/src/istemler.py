"""İstem şablonlarını doldurma ve JSON şemaları.

Öğretmen istemi doldurulmaz: dosya olduğu gibi gider (yalnızca davranış).
Öğrenci istemlerine adım değerleri ve son cevap KONMAZ (istisna: kontrol_isteyen + hepsi_biliyor
açılışında son cevap).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .ortak import istem_oku, istem_yolu, sablon_doldur, yaml_oku
from .sayilar import bicimle

OGRENCI_SEMASI = {
    "type": "object",
    "properties": {
        "denenen_adim": {"type": ["integer", "null"]},
        "verilen_deger": {"type": ["number", "null"]},
        "kilit_acildi": {"type": "boolean"},
        "israr_taktigi": {"type": ["string", "null"]},
        "tahmin_listesi": {"anyOf": [{"type": "array", "items": {"type": "number"}}, {"type": "null"}]},
        "kapatmak_istiyor": {"type": "boolean"},
        "mesaj": {"type": "string"},
    },
    "required": ["denenen_adim", "verilen_deger", "kilit_acildi", "israr_taktigi", "tahmin_listesi",
                 "kapatmak_istiyor", "mesaj"],
    "additionalProperties": False,
}

ACILIS_EK_SEMASI = {
    "type": "object",
    "properties": {"on_ek": {"type": "string"}, "son_ek": {"type": "string"}},
    "required": ["on_ek", "son_ek"],
    "additionalProperties": False,
}

ACILIS_TAM_SEMASI = {
    "type": "object",
    "properties": {"mesaj": {"type": "string"}, "verilen_deger": {"type": ["number", "null"]}},
    "required": ["mesaj", "verilen_deger"],
    "additionalProperties": False,
}


def ogrenci_semasi(israr_katalogu: list[str]) -> dict:
    sema = {**OGRENCI_SEMASI, "properties": dict(OGRENCI_SEMASI["properties"])}
    sema["properties"]["israr_taktigi"] = {"anyOf": [{"type": "string", "enum": list(israr_katalogu)}, {"type": "null"}]}
    return sema


def acilis_semasi(acilis: str) -> dict:
    return ACILIS_EK_SEMASI if acilis in ("kopyala_yapistir", "cevabi_ne") else ACILIS_TAM_SEMASI


def acilis_birlestir(js: dict, soru: str) -> str:
    """on_ek + soru + son_ek. Soru metni birebir korunur.

    VARSAYIM: ek boş değilse ve boşlukla bitmiyor/başlamıyorsa araya tek boşluk konur.
    """
    on, son = (js.get("on_ek") or "").rstrip(" "), (js.get("son_ek") or "").lstrip(" ")
    parcalar = []
    if on.strip():
        parcalar.append(on if on.endswith(("\n", " ")) else on + " ")
    parcalar.append(soru)
    if son.strip():
        parcalar.append(son if son.startswith(("\n", " ")) else " " + son)
    return "".join(parcalar)


@dataclass
class Istemler:
    ogretmen_sistem: str
    ogrenci_tur: str
    acilis_bolumleri: dict[str, str]
    tanimlar: dict
    maks_ogrenci_kelime: int

    @classmethod
    def yukle(cls, cfg: dict) -> "Istemler":
        return cls(
            ogretmen_sistem=istem_oku(istem_yolu(cfg, "ogretmen_sistem")),
            ogrenci_tur=istem_oku(istem_yolu(cfg, "ogrenci_tur")),
            acilis_bolumleri=_bolumlere_ayir(istem_oku(istem_yolu(cfg, "ogrenci_acilis"))),
            tanimlar=yaml_oku(istem_yolu(cfg, "ogrenci_tanimlar")),
            maks_ogrenci_kelime=cfg["maks_ogrenci_kelime"],
        )

    # ------------------------------------------------------------ ortak parçalar
    def hata_aciklamasi(self, hata_tipi: str | None) -> str:
        return self.tanimlar["hata_tipleri"].get(hata_tipi or "", hata_tipi or "")

    def uslup_metni(self, senaryo: dict) -> str:
        u, t = senaryo["uslup"], self.tanimlar["uslup"]
        return " ".join(x for x in (t["yazim"][u["yazim"]], t["baglam"][u["baglam"]], t["ton"][u["ton"]]) if x)

    def persona_metni(self, senaryo: dict) -> str:
        return self.tanimlar["davranislar"][senaryo["persona"]["davranis"]]

    def israr_metni(self, senaryo: dict, durum=None) -> str:
        p = senaryo["persona"]
        if p["davranis"] != "israrci":
            return "Israr taktiği kullanmazsın; israr_taktigi her zaman null olmalı."
        taktikler = p["israr_taktikleri"]
        kalan = durum.israr_kalan if durum else len(taktikler)
        sira = durum.siradaki_taktik if durum else (taktikler[0] if taktikler else None)
        if kalan <= 0 or sira is None:
            return "Israr hakkın bitti; artık ısrar etme, israr_taktigi null olmalı ve normal şekilde çalış."
        return (f"Kalan ısrar hakkın: {kalan}. Israr edeceğin zaman sıradaki taktiğin '{sira}': "
                f"{self.tanimlar['israr_taktikleri'][sira]} Bu taktiği kullandığın mesajda israr_taktigi "
                f"alanına '{sira}' yaz. Bir mesajda en fazla bir taktik kullan.")

    def bilgi_durumu_metni(self, durum) -> str:
        satirlar = []
        d = self.tanimlar["adim_durumlari"]
        for a in durum.adimlar:
            if a.durum == "hatali":
                aciklama = d["hatali_duzeltildi"] if a.hata_duzeltildi else \
                    d["hatali"].replace("{hata_aciklamasi}", self.hata_aciklamasi(a.hata_tipi))
                etiket = "hatalı"
            elif a.durum == "kilitli":
                aciklama = d["kilit_acik"] if a.kilit_acildi else d["kilitli"]
                etiket = "kilitli"
            else:
                aciklama, etiket = d["biliyor"], "biliyor"
            tamam = " [TAMAMLANDI]" if a.tamamlandi else ""
            satirlar.append(f"{a.no}. adım ({etiket}){tamam}: {a.alt_soru_tr} — {aciklama}")
        return "\n".join(satirlar)

    # ------------------------------------------------------------ öğrenci tur istemi
    def ogrenci_tur_istemi(self, senaryo: dict, durum) -> str:
        aktif = durum.adim(durum.aktif_adim)
        aktif_metin = (f"{aktif.no}. adım — {aktif.alt_soru_tr}" if aktif else
                       "Bütün adımları tamamladın; son cevabı söyledin.")
        return sablon_doldur(self.ogrenci_tur, {
            "soru_tr": senaryo["soru_tr"],
            "adim_sayisi": durum.n,
            "bilgi_durumu": self.bilgi_durumu_metni(durum),
            "aktif_adim": aktif_metin,
            "persona": self.persona_metni(senaryo),
            "israr": self.israr_metni(senaryo, durum),
            "uslup": self.uslup_metni(senaryo),
            "maks_kelime": self.maks_ogrenci_kelime,
        })

    # ------------------------------------------------------------ açılış istemi
    def acilis_istemi(self, senaryo: dict) -> str:
        p = senaryo["persona"]
        bolum = p["acilis"]
        alanlar = {
            "soru_tr": senaryo["soru_tr"],
            "uslup": self.uslup_metni(senaryo),
            "persona": self.persona_metni(senaryo),
            "maks_kelime": self.maks_ogrenci_kelime,
        }
        if bolum == "yanlis_denemeli":
            h = next(a for a in senaryo["adimlar"] if a["durum"] == "hatali")
            alanlar.update(hatali_alt_soru=f"{h['no']}. adım — {h['alt_soru_tr']}",
                           hata_aciklamasi=self.hata_aciklamasi(h.get("hata_tipi")))
        elif bolum == "kontrol_isteyen":
            bolum = f"kontrol_isteyen__{senaryo['bilgi_sablonu']}"
            if senaryo["bilgi_sablonu"] == "hepsi_biliyor":
                alanlar["son_cevap"] = bicimle(senaryo["son_cevap"])
        metin = self.acilis_bolumleri["ortak"] + "\n\n" + self.acilis_bolumleri[bolum]
        return sablon_doldur(metin, alanlar)


def _bolumlere_ayir(metin: str) -> dict[str, str]:
    bolumler: dict[str, str] = {}
    ad = None
    satirlar: list[str] = []
    for satir in metin.splitlines():
        m = re.fullmatch(r"===\s*(\w+)\s*===", satir.strip())
        if m:
            if ad:
                bolumler[ad] = "\n".join(satirlar).strip()
            ad, satirlar = m.group(1), []
        else:
            satirlar.append(satir)
    if ad:
        bolumler[ad] = "\n".join(satirlar).strip()
    return bolumler
