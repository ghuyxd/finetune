"""
Script kiểm tra xem tokenizer của các mô hình ≤3B có hỗ trợ
Tai Viet Unicode block (U+AA80–U+AADF) không.

Chạy: python check_unicode.py
"""

from transformers import AutoTokenizer

# Danh sách model cần kiểm tra (≤3B)
MODELS = [
    "Qwen/Qwen2.5-3B",
    "Qwen/Qwen2.5-1.5B",
    "google/gemma-3-1b-pt",
    "microsoft/phi-2",                   # 2.7B
    "meta-llama/Llama-3.2-3B",
    "meta-llama/Llama-3.2-1B",
    "vinai/PhoGPT-3B-Instruct",          # model TV chuyên biệt
]

# Sample Tai Viet
TAI_VIET_SAMPLES = [
    "ꪮꪱꪚ ꪤꪲꪙ",          # từ mẫu từ repair_tavt
    "ꪵꪀꪫꪱ ꪁꪷꪙ",
    "ꪣꪴ ꪣꪽ ꪀꪷꪙ",
]
VIET_SAMPLE = "Xin chào, tôi học tiếng dân tộc Thái."

TAI_VIET_RANGE = range(0xAA80, 0xAAE0)


def check_model(model_id: str):
    print(f"\n{'='*60}")
    print(f"Model: {model_id}")
    print(f"{'='*60}")
    try:
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    except Exception as e:
        print(f"  Khong tai duoc tokenizer: {e}")
        return

    vocab = tok.get_vocab()
    vocab_size = len(vocab)
    print(f"  Vocab size: {vocab_size:,}")

    # 1. Kiem tra tung ky tu Tai Viet trong vocab
    found_chars = []
    for cp in TAI_VIET_RANGE:
        ch = chr(cp)
        for token in vocab:
            if ch in token:
                found_chars.append(ch)
                break

    pct = len(found_chars) / len(TAI_VIET_RANGE) * 100
    print(f"  Tai Viet chars in vocab: {len(found_chars)}/{len(TAI_VIET_RANGE)} ({pct:.1f}%)")

    # 2. Tokenize sample
    for sample in TAI_VIET_SAMPLES:
        ids = tok.encode(sample, add_special_tokens=False)
        tokens = tok.convert_ids_to_tokens(ids)
        unk_id = tok.unk_token_id
        has_unk = unk_id is not None and unk_id in ids
        flag = "[UNK!]" if has_unk else "[OK]"
        print(f"  {flag}  '{sample}'")
        print(f"       tokens({len(ids)}): {tokens[:12]}")

    # 3. Tokenize tieng Viet
    ids_vi = tok.encode(VIET_SAMPLE, add_special_tokens=False)
    print(f"  VI ({len(ids_vi)} tokens): '{VIET_SAMPLE}'")

    # 4. Danh gia
    if pct >= 80:
        verdict = "[XANH] HO TRO TOT Tai Viet"
    elif pct >= 30:
        verdict = "[VANG] HO TRO PARTIAL"
    else:
        verdict = "[DO] KHONG HO TRO Tai Viet (can extend vocab)"
    print(f"  => {verdict}")


if __name__ == "__main__":
    print("Kiem tra ho tro Unicode Tai Viet (U+AA80-U+AADF) trong tokenizer")
    for m in MODELS:
        check_model(m)
    print("\nDone.")
