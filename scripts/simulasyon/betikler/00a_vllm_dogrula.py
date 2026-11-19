#!/usr/bin/env python3
"""Bölüm 3.1–3.2 doğrulaması: GPU sunucusunda, vLLM ayağa kalktıktan sonra çalıştırın.

Kontroller
1. Sunucu ve model adı (/v1/models).
2. Düşünme AÇIK: iz `reasoning_content`/`reasoning` alanında ayrı geliyor mu, içerikte <think> kalıyor mu?
3. Düşünme KAPALI: iz boş mu, içerik dolu mu?
4. JSON şeması zorlama: response_format / structured_outputs / guided_json — hangisi çalışıyor?
5. Çok turlu geçmişte (izsiz assistant mesajı) düşünme açık çağrı çalışıyor mu?

Herhangi bir zorunlu kontrol başarısızsa çıkış kodu 1'dir: talimat gereği DURUN ve raporlayın.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.istemler import ogrenci_semasi  # noqa: E402
from src.llm_istemci import JSON_MODLARI, LLMIstemci, iz_ayir, json_coz  # noqa: E402
from src.ortak import config_yukle  # noqa: E402

SORU = "Natalia nisan ayında 48 arkadaşına toka sattı, mayısta bunun yarısı kadar sattı. Toplam kaç toka sattı?"


async def main_async(cfg: dict) -> int:
    import openai
    ist = LLMIstemci(cfg)
    c = ist.istemci
    sonuc: dict[str, object] = {}
    hata = 0

    def yaz(ad: str, ok: bool, detay: str = "", zorunlu: bool = True) -> None:
        nonlocal hata
        sonuc[ad] = ok
        if not ok and zorunlu:
            hata += 1
        print(f"[{'OK ' if ok else ('HATA' if zorunlu else 'UYARI')}] {ad}  {detay}")

    # 1 -------------------------------------------------------------------------
    try:
        modeller = [m.id for m in (await c.models.list()).data]
        yaz("sunucu_ve_model", cfg["model"] in modeller, f"sunucudaki modeller: {modeller}")
    except Exception as e:  # noqa: BLE001
        yaz("sunucu_ve_model", False, repr(e))
        return 1

    std, ekstra = ist._ornekleme(cfg["ogretmen_ornekleme"])

    async def cagri(mesajlar, dusunme: bool, **kw):
        return await c.chat.completions.create(
            model=cfg["model"], messages=mesajlar, **{**std, "max_tokens": kw.pop("max_tokens", std.get("max_tokens", 2000))},
            extra_body={**ekstra, "chat_template_kwargs": {"enable_thinking": dusunme}, **kw.pop("extra_body", {})}, **kw)

    # 2 -------------------------------------------------------------------------
    r = await cagri([{"role": "system", "content": "Kısa cevap ver."}, {"role": "user", "content": SORU}], True)
    m = r.choices[0].message
    alanlar = {"reasoning_content": bool(getattr(m, "reasoning_content", None) or (m.model_extra or {}).get("reasoning_content")),
               "reasoning": bool(getattr(m, "reasoning", None) or (m.model_extra or {}).get("reasoning"))}
    ham_icerik = m.content or ""
    iz, icerik = iz_ayir(m)
    yaz("dusunme_acik_iz_ayri_alanda", any(alanlar.values()), f"alanlar={alanlar}, finish={r.choices[0].finish_reason}")
    yaz("dusunme_acik_icerikte_think_yok", "<think>" not in ham_icerik and "</think>" not in ham_icerik,
        "içerikte <think> varsa --reasoning-parser eksik/yanlış")
    yaz("dusunme_acik_icerik_dolu", bool(icerik), f"iz {len(iz.split())} kelime, içerik: {icerik[:120]!r}")

    # 3 -------------------------------------------------------------------------
    r = await cagri([{"role": "user", "content": SORU}], False, max_tokens=300)
    iz2, icerik2 = iz_ayir(r.choices[0].message)
    yaz("dusunme_kapali_iz_bos", not iz2, f"iz={iz2[:80]!r}")
    yaz("dusunme_kapali_icerik_dolu", bool(icerik2), f"içerik: {icerik2[:120]!r}")

    # 4 -------------------------------------------------------------------------
    sema = ogrenci_semasi(cfg["israr_taktikleri"])
    calisan = []
    for mod in JSON_MODLARI:
        kw, ek = ist._json_kwargs(mod, sema)
        try:
            r = await cagri([{"role": "system", "content": "Bir öğrencisin. Yalnızca JSON döndür."},
                             {"role": "user", "content": "Mayısta kaç toka sattı?"}], False, max_tokens=300,
                            extra_body=ek, **kw)
            js, h = json_coz(r.choices[0].message.content)
            ok = js is not None and set(js) == set(sema["required"])
            yaz(f"json_{mod}", ok, f"{h or ''} {json.dumps(js, ensure_ascii=False)[:150] if js else (r.choices[0].message.content or '')[:150]}",
                zorunlu=False)
            if ok:
                calisan.append(mod)
        except openai.BadRequestError as e:
            yaz(f"json_{mod}", False, f"BadRequest: {str(e)[:200]}", zorunlu=False)
    yaz("json_en_az_bir_yontem", bool(calisan), f"çalışanlar: {calisan}")

    # 5 -------------------------------------------------------------------------
    r = await cagri([{"role": "system", "content": "Kısa cevap ver."}, {"role": "user", "content": SORU},
                     {"role": "assistant", "content": "Önce mayısta kaç sattığını bulalım. 48'in yarısı kaç?"},
                     {"role": "user", "content": "24"}], True)
    iz3, icerik3 = iz_ayir(r.choices[0].message)
    yaz("cok_turlu_dusunme", bool(iz3) and bool(icerik3), f"içerik: {icerik3[:120]!r}")

    await ist.kapat()
    print("\nÖZET:", json.dumps(sonuc, ensure_ascii=False))
    if calisan:
        print(f"Öneri: config.yaml → json_zorlama: {calisan[0]}")
    if hata:
        print("\nZorunlu kontrollerden en az biri başarısız: simülasyona geçmeden önce durup raporlayın.")
    return 1 if hata else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    sys.exit(asyncio.run(main_async(config_yukle(args.config))))


if __name__ == "__main__":
    main()
