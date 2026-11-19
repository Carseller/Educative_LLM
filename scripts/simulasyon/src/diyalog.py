"""Tek diyalog döngüsü, mesaj yapısı ve rol çevirme."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .durum import OgrenciDurumu
from .hakem import Hakem
from .istemler import Istemler, ogrenci_semasi
from .llm_istemci import AgHatasi
from .ortak import istek_seed, simdi


@dataclass
class Mesaj:
    rol: str                       # "ogrenci" | "ogretmen"
    icerik: str
    iz: str | None = None          # yalnızca öğretmen; geçmişe ASLA girmez
    meta: dict | None = None       # öğrenci: hakemden geçmiş JSON; öğretmen: o anki aktif adım vb.
    deneme_sayisi: int | None = None

    def kayit(self) -> dict:
        d = {"rol": self.rol, "icerik": self.icerik}
        if self.rol == "ogretmen":
            d["iz"] = self.iz
        if self.meta is not None:
            d["meta"] = self.meta
        if self.deneme_sayisi is not None:
            d["deneme_sayisi"] = self.deneme_sayisi
        return d


def ogretmene_gecmis(mesajlar: list[Mesaj]) -> list[dict]:
    """Öğrenci → user, öğretmen → assistant. Yalnızca içerik; önceki izler gitmez."""
    return [{"role": "user" if m.rol == "ogrenci" else "assistant", "content": m.icerik} for m in mesajlar]


def ogrenciye_gecmis(mesajlar: list[Mesaj]) -> list[dict]:
    """Roller çevrilir: öğretmen → user, öğrenci → assistant. Öğretmen izi asla gitmez."""
    return [{"role": "user" if m.rol == "ogretmen" else "assistant", "content": m.icerik} for m in mesajlar]


@dataclass
class DiyalogAyar:
    maks_ogretmen_turu: int = 8
    deneme_sayisi: int = 3
    seed: int = 42


@dataclass
class DiyalogSonucu:
    id: str
    durum: str                     # "kaydedildi" | "atildi" | "ag_hatasi"
    bitis: str | None = None
    neden: str | None = None
    mesajlar: list[Mesaj] = field(default_factory=list)
    ogrenci_durumu: dict | None = None
    olaylar: list = field(default_factory=list)
    baslangic: str = ""
    bitis_zamani: str = ""


LogFn = Callable[[dict], None]
EkranFn = Callable[[str], None]


async def diyalog_calistir(senaryo: dict, istemci, hakem: Hakem, istemler: Istemler, ayar: DiyalogAyar,
                           log_yaz: LogFn, calisma_id: str, ekran: EkranFn | None = None) -> DiyalogSonucu:
    sid = senaryo["id"]
    sonuc = DiyalogSonucu(id=sid, durum="kaydedildi", baslangic=simdi())
    mesajlar = [Mesaj("ogrenci", senaryo["acilis_mesaji"], meta={"acilis": True})]
    durum = OgrenciDurumu.baslat(senaryo)
    sema = ogrenci_semasi(hakem.israr_katalogu)
    yaz = ekran or (lambda _: None)
    yaz(f"\n{'=' * 80}\nSENARYO {sid}  şablon={senaryo['bilgi_sablonu']}  persona={senaryo['persona']}\n"
        f"ÖĞRENCİ (açılış): {senaryo['acilis_mesaji']}\nDURUM: {durum.ozet()}")

    def bitir(durum_kodu: str, bitis: str | None = None, neden: str | None = None) -> DiyalogSonucu:
        sonuc.durum, sonuc.bitis, sonuc.neden = durum_kodu, bitis, neden
        sonuc.mesajlar, sonuc.ogrenci_durumu, sonuc.olaylar = mesajlar, durum.ozet(), durum.olaylar
        sonuc.bitis_zamani = simdi()
        yaz(f"--> BİTİŞ: {durum_kodu} {bitis or ''} {neden or ''}")
        return sonuc

    ogretmen_tur = 0
    try:
        # Son cevap ya da kapatma, son turda gelse bile öğretmene bir kapanış turu hakkı tanınır.
        # VARSAYIM: bu ek tur maks_ogretmen_turu sınırının dışında sayılır.
        while ogretmen_tur < ayar.maks_ogretmen_turu or durum.kapanis_bekliyor:
            # ---------------------------------------------------------- öğretmen
            kabul = None
            for deneme in range(ayar.deneme_sayisi):
                y = await istemci.ogretmen(
                    istemler.ogretmen_sistem, ogretmene_gecmis(mesajlar),
                    seed=istek_seed(ayar.seed, sid, "ogretmen", ogretmen_tur, deneme),
                    sahte_baglam={"senaryo": senaryo, "durum": durum, "mesajlar": mesajlar,
                                  "tur": ogretmen_tur, "deneme": deneme})
                sorunlar = hakem.ogretmen_kontrol(y.icerik, y.iz, senaryo, mesajlar, durum, ogretmen_tur)
                log_yaz({"diyalog_id": sid, "calisma_id": calisma_id, "rol": "ogretmen", "ogretmen_tur": ogretmen_tur,
                         "deneme": deneme, "kabul": not sorunlar, "sorunlar": list(sorunlar),
                         "uyarilar": sorunlar.uyarilar, "bilgi": sorunlar.bilgi, "baglam_uzunlugu": len(mesajlar),
                         "iz": y.iz, "cevap": y.icerik, "finish_reason": y.finish_reason, "ag_hatasi": y.ag_hatasi,
                         "sure_sn": round(y.sure_sn, 3), "kullanim": y.kullanim, "zaman": simdi()})
                yaz(f"\n--- ÖĞRETMEN tur={ogretmen_tur} deneme={deneme} → "
                    f"{'KABUL' if not sorunlar else 'RET ' + str(list(sorunlar))}"
                    f"{'  uyarı=' + str(sorunlar.uyarilar) if sorunlar.uyarilar else ''}\n"
                    f"[iz] {y.iz}\n[cevap] {y.icerik}")
                if not sorunlar:
                    kabul = (y, deneme + 1)
                    break
            if kabul is None:
                return bitir("atildi", neden="ogretmen_3_deneme")
            y, n_deneme = kabul
            mesajlar.append(Mesaj("ogretmen", y.icerik, iz=y.iz, deneme_sayisi=n_deneme,
                                  meta={"aktif_adim": durum.aktif_adim}))
            ogretmen_tur += 1
            durum.ogretmen_turu_eklendi()
            if durum.tamamlandi:
                return bitir("kaydedildi", bitis=hakem.bitis_etiketi(durum))
            if ogretmen_tur >= ayar.maks_ogretmen_turu:
                # VARSAYIM: tur sınırında son öğretmen mesajına öğrenci cevabı üretilmez (eğitimde kullanılmaz).
                break

            # ---------------------------------------------------------- öğrenci
            kabul_js = None
            for deneme in range(ayar.deneme_sayisi):
                sistem = istemler.ogrenci_tur_istemi(senaryo, durum)
                y = await istemci.ogrenci_json(
                    sistem, ogrenciye_gecmis(mesajlar), sema,
                    seed=istek_seed(ayar.seed, sid, "ogrenci", ogretmen_tur, deneme),
                    sahte_baglam={"senaryo": senaryo, "durum": durum, "mesajlar": mesajlar, "deneme": deneme})
                sorunlar = hakem.ogrenci_kontrol(y.js, senaryo, mesajlar, durum)
                if y.json_hatasi:
                    sorunlar.bilgi["ayristirma"] = y.json_hatasi
                log_yaz({"diyalog_id": sid, "calisma_id": calisma_id, "rol": "ogrenci", "ogretmen_tur": ogretmen_tur,
                         "deneme": deneme, "kabul": not sorunlar, "sorunlar": list(sorunlar),
                         "uyarilar": sorunlar.uyarilar, "bilgi": sorunlar.bilgi, "baglam_uzunlugu": len(mesajlar),
                         "js": y.js, "ham": y.icerik if y.js is None else None, "finish_reason": y.finish_reason,
                         "ag_hatasi": y.ag_hatasi, "sure_sn": round(y.sure_sn, 3), "durum": durum.ozet(),
                         "zaman": simdi()})
                yaz(f"\n--- ÖĞRENCİ deneme={deneme} → {'KABUL' if not sorunlar else 'RET ' + str(list(sorunlar))}"
                    f"{'  uyarı=' + str(sorunlar.uyarilar) if sorunlar.uyarilar else ''}\n[json] {y.js or y.icerik}")
                if not sorunlar:
                    kabul_js = (y.js, deneme + 1)
                    break
            if kabul_js is None:
                return bitir("atildi", neden="ogrenci_3_deneme")
            js, n_deneme = kabul_js
            mesajlar.append(Mesaj("ogrenci", js["mesaj"], meta=js, deneme_sayisi=n_deneme))
            durum.guncelle(js)
            yaz(f"DURUM: {durum.ozet()}")
            # Öğrenci bitirdiyse/kapattıysa döngü öğretmenin kapanış turuyla devam eder.
    except AgHatasi as e:
        # Ağ hatası hakem reddi değildir: diyalog atılmaz, sonraki çalıştırmada yeniden denenir.
        return bitir("ag_hatasi", neden=str(e)[:300])
    return bitir("kaydedildi", bitis="tur_siniri")
