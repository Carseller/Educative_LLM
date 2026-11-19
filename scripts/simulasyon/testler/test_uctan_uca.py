"""01 → 05 boru hattını küçük bir veri fikstürü ve sahte istemciyle uçtan uca çalıştırır."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

KOK = Path(__file__).resolve().parent.parent
FIKSTUR = Path(__file__).resolve().parent / "veri"


def _calistir(betik: str, cfg: Path, *ek: str) -> str:
    r = subprocess.run([sys.executable, str(KOK / "betikler" / betik), "--config", str(cfg), *ek],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"{betik} başarısız:\n{r.stdout}\n{r.stderr}"
    return r.stdout


def _oku(yol: Path) -> list[dict]:
    return [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines() if s.strip()]


def test_boru_hatti(tmp_path):
    cfg = yaml.safe_load((KOK / "config.yaml").read_text(encoding="utf-8"))
    cfg["dizinler"] = {"veri": str(tmp_path / "veri"), "log": str(tmp_path / "loglar"), "istem": str(KOK / "istemler")}
    cfg["eszamanli"] = 4
    cfg_yol = tmp_path / "config.yaml"
    cfg_yol.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    v = tmp_path / "veri"

    cikti = _calistir("01_sorulari_hazirla.py", cfg_yol, "--yerel-dizin", str(FIKSTUR))
    assert "TR[i] = EN[i+1]" in cikti
    sorular = _oku(v / "sorular_train.jsonl")
    assert sorular and all("_train_" in s["id"] for s in sorular)
    assert all("_test_" in s["id"] for s in _oku(v / "sorular_test.jsonl"))
    # EN satır 0'ın (Natalia) TR karşılığı yok
    assert {"id": "gsm8k_train_0", "bolum": "train", "neden": "tr_karsiligi_yok"} in _oku(v / "elenen_sorular.jsonl")

    _calistir("02a_senaryo_olustur.py", cfg_yol)
    senaryolar = _oku(v / "senaryolar.jsonl")
    assert len(senaryolar) == 3 * len(sorular)
    assert not any("_test_" in s["id"] for s in senaryolar)

    _calistir("02b_acilis_uret.py", cfg_yol, "--sahte")
    acilisli = _oku(v / "senaryolar_acilisli.jsonl")
    assert acilisli and all(s["acilis_mesaji"] for s in acilisli)
    for s in acilisli:
        if s["persona"]["acilis"] in ("kopyala_yapistir", "cevabi_ne"):
            assert s["soru_tr"] in s["acilis_mesaji"]

    _calistir("03_simulasyon.py", cfg_yol, "--sahte")
    ham = _oku(v / "ham_diyaloglar.jsonl")
    assert ham
    assert {"id", "senaryo", "bitis", "mesajlar", "istem_surumleri", "model", "ornekleme"} <= set(ham[0])
    # kaldığı yerden devam: ikinci çalıştırma yeni diyalog üretmez
    n_ham = len(ham)
    _calistir("03_simulasyon.py", cfg_yol, "--sahte")
    assert len(_oku(v / "ham_diyaloglar.jsonl")) == n_ham

    _calistir("04_pilot_rapor.py", cfg_yol)
    assert (tmp_path / "loglar" / "pilot_rapor.md").exists()

    _calistir("05_egitim_formatina_cevir.py", cfg_yol)
    sft = _oku(v / "sft.jsonl")
    assert sft
    anahtarlar = ["id", "kategori", "ders", "sinif", "zorluk", "ogrenci_tipi", "kaynak", "dogru_cevap",
                  "anahtar_adim", "rehber_surumu", "messages"]
    for o in sft:
        assert list(o) == anahtarlar
        assert o["messages"][0]["role"] == "user" and o["messages"][-1]["role"] == "assistant"
        assert all(m["role"] != "system" for m in o["messages"])
        asistanlar = [m for m in o["messages"] if m["role"] == "assistant"]
        assert "reasoning_content" in asistanlar[-1]
        assert all("reasoning_content" not in m for m in asistanlar[:-1])
        assert o["kategori"] in {"cozum_kontrolu", "manipulasyon", "kademeli_destek", "yonlendirme"}
    for d in _oku(v / "dpo_adaylari.jsonl"):
        assert {"prompt", "chosen", "rejected", "red_nedeni"} <= set(d) and d["red_nedeni"]
