"""GSM8K (İngilizce) ve GSM8K-TR socratic alt kümelerini repoya koymak için indirir.

Bir kez kendi bilgisayarında çalıştır, çıkan kaynak_veri/ klasörünü commit'le.
Sunucuda tekrar çalıştırmaya gerek yok.

Kurulum:  pip install datasets huggingface_hub
Kullanım: python kaynak_veriyi_indir.py
"""
import hashlib
import os

from datasets import load_dataset
from huggingface_hub import HfApi

HEDEF = "kaynak_veri"

# (hf_deposu, alt_kume, bölüm, dosya_adı)
KAYNAKLAR = [
    ("openai/gsm8k", "socratic", "train", "gsm8k_en_socratic_train.jsonl"),
    ("openai/gsm8k", "socratic", "test", "gsm8k_en_socratic_test.jsonl"),
    ("malhajar/gsm8k-tr", "socratic", "train", "gsm8k_tr_socratic_train.jsonl"),
    ("malhajar/gsm8k-tr", "socratic", "test", "gsm8k_tr_socratic_test.jsonl"),
]


def sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def main():
    os.makedirs(HEDEF, exist_ok=True)
    api = HfApi()
    surumler = {}
    satirlar = []
    for depo, alt, bolum, dosya in KAYNAKLAR:
        if depo not in surumler:
            surumler[depo] = api.dataset_info(depo).sha   # o anki commit'e sabitle
        ds = load_dataset(depo, alt, split=bolum, revision=surumler[depo])
        yol = os.path.join(HEDEF, dosya)
        ds.to_json(yol, lines=True, force_ascii=False)
        boyut = os.path.getsize(yol) / 1e6
        print(f"{dosya}: {len(ds)} satır, {boyut:.1f} MB")
        satirlar.append(f"| `{dosya}` | `{depo}` | {alt} / {bolum} | `{surumler[depo][:12]}` | {len(ds)} | `{sha256(yol)[:16]}` |")

    # Eşleştirme için hızlı kontrol: satır sayıları aynı mı
    for bolum in ("train", "test"):
        en = sum(1 for _ in open(os.path.join(HEDEF, f"gsm8k_en_socratic_{bolum}.jsonl"), encoding="utf-8"))
        tr = sum(1 for _ in open(os.path.join(HEDEF, f"gsm8k_tr_socratic_{bolum}.jsonl"), encoding="utf-8"))
        durum = "tamam" if en == tr else "FARKLI: eşleştirme sıra ile yapılamaz, kontrol et"
        print(f"{bolum}: İng {en}, Tr {tr} -> {durum}")

    with open(os.path.join(HEDEF, "KAYNAKLAR.md"), "w", encoding="utf-8") as f:
        f.write("# Kaynak veriler\n\n")
        f.write("Bu klasördeki dosyalar `kaynak_veriyi_indir.py` ile indirildi. Elle düzenlenmez.\n\n")
        f.write("| Dosya | Kaynak | Alt küme / bölüm | Commit | Satır | SHA-256 (ilk 16) |\n")
        f.write("|---|---|---|---|---|---|\n")
        f.write("\n".join(satirlar) + "\n\n")
        f.write("## Lisanslar\n\n")
        f.write("- GSM8K: MIT Lisansı, Cobbe vd. (2021), *Training Verifiers to Solve Math Word Problems*, arXiv:2110.14168. https://huggingface.co/datasets/openai/gsm8k\n")
        f.write("- GSM8K-TR: MIT Lisansı, Mohamad Alhajar. https://huggingface.co/datasets/malhajar/gsm8k-tr\n\n")
        f.write("Test bölümleri yalnızca değerlendirme içindir; simülasyona girmez.\n")
    print(f"\n{HEDEF}/KAYNAKLAR.md yazıldı.")


if __name__ == "__main__":
    main()
